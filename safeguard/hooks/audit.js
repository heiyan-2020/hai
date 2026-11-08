import { TraceFile, readTrace } from './trace-io.js'
import { COVERAGE, enforceRules, readRules, hash } from './common.js'
import { diagnose, formatFinding } from './sources.js'
const join = (base, rest) => base.replace(/[\\/]$/, '') + '/' + rest

export function createAudit(options) {
  const state = {}
    state.options = options; state.files = new Map(); state.notified = new Set(); state.seen = new Set()
    state.checked = 0; state.findings = []; state.busy = false; state.session = null; state.cwd = null
    state.main = null; state.revision = 0; state.timer = null; state.coverageNotes = new Set()
  return state
}

export async function auditStart($, state, e) {
    state.session = await $.session.id(); state.cwd = e.cwd
    if (!state.options.audit) return
    if (e.isInteractive && !state.timer) state.timer = $.clock.every(1000, () => { void auditPoll($, state) })
}

export function registerTrace(state, path, cwd) {
    if (typeof path !== 'string' || !path.endsWith('.jsonl')) return
    state.main = state.main || path
    if (!state.files.has(path)) state.files.set(path, { trace: new TraceFile(path), cwd: cwd || state.cwd })
}

export async function discoverTraces($, state) {
    if (!state.main && state.session && state.cwd) {
      const home = await $.env.get('HOME') || await $.env.get('USERPROFILE')
      const root = await $.env.get('CLAUDE_CONFIG_DIR') || (home ? join(home, '.claude') : null)
      if (!root) return
      const projects = join(root, 'projects'), filename = state.session + '.jsonl'
      const guess = join(projects, state.cwd.replace(/[^A-Za-z0-9]/g, '-') + '/' + filename)
      if (await $.fs.exists(guess)) registerTrace(state, guess, state.cwd)
      else {
        try {
          for (const entry of (await $.fs.list(projects)).slice(0, 256)) {
            const path = join(projects, entry.name + '/' + filename)
            if (await $.fs.exists(path)) { registerTrace(state, path, state.cwd); break }
          }
        } catch { /* The first request's file may not exist yet. */ }
      }
    }
    if (state.main) {
      const sub = state.main.slice(0, -6) + '/subagents'
      try {
        const files = (await $.fs.list(sub)).filter(x => x.name.endsWith('.jsonl'))
        if (files.length > 32) await auditNote($, state, 'coverage_unknown', 'More than 32 subagent logs; not all can be watched in this session.')
        for (const file of files.slice(0, 32)) {
          const path = join(sub, file.name)
          if (!state.files.has(path)) state.files.set(path, { trace: new TraceFile(path), cwd: state.cwd })
        }
      } catch { /* No subagent log directory is normal. */ }
    }
}

export async function auditNote($, state, status, message, extra = {}) {
    const id = await hash({ status, message, findings: extra.findings || [] })
    if (state.seen.has(id)) return
    state.seen.add(id); state.revision++
    state.findings.push({ id, status, message, ...extra })
    if (state.findings.length > 20) state.findings.shift()
    if (!state.notified.has(id)) {
      $.ui.toast('Safeguard audit warning (after send). /safeguard-audit for details.', { timeoutMs: 4000 })
      state.notified.add(id)
    }
}

export async function auditPoll($, state) {
    if (!state.options.audit || state.busy || !state.session) return
    state.busy = true
    const oldRevision = state.revision, oldChecked = state.checked
    try {
      await discoverTraces($, state)
      for (const [path, value] of state.files) {
        const trace = value.trace
        try { await readTrace($, trace) }
        catch { await auditNote($, state, 'coverage_unknown', 'A trace could not be read or changed unexpectedly; audit coverage is unknown.', { file: path }); continue }
        if (trace.replay.compactions) await auditNote($, state, 'coverage_gap', 'Compaction detected. Its model requests were not recorded in the tested CLI and cannot be certified by this audit.', { file: path })
        for (const key of trace.replay.order) {
          if (trace.audited.has(key)) continue
          try {
            const result = await trace.replay.reconstruct(key)
            const findings = await diagnose($, result.request, value.cwd)
            let policy = null
            try { enforceRules(await readRules($, state.options), result.request, 'context') }
            catch { policy = 'A context rule matched or its configuration was invalid.' }
            state.checked++; state.revision++; trace.audited.add(key)
            if (findings.length || policy) await auditNote($, state, 'finding_after_send', policy || 'Chinese was found in a request that has ALREADY BEEN SENT.', { requestId: result.id, file: path, integrity: 'sha256_verified', findings })
          } catch { /* Dependencies may be appended by a later log flush. */ }
        }
        if (trace.replay.errors.length) await auditNote($, state, 'incomplete_trace', 'Invalid JSONL records; this log cannot be certified.', { file: path })
      }
      if (state.checked !== oldChecked || state.revision !== oldRevision) await persistAudit($, state)
    } catch {
      try { await auditNote($, state, 'coverage_unknown', 'Audit processing failed; no clean result can be inferred.') } catch { /* No terminal writes. */ }
    } finally { state.busy = false }
}

export async function persistAudit($, state) {
    if (!state.session) return
    const key = 'audit:' + state.session
    await $.store.set(key, { session: state.session, updated: Date.now(), checked: state.checked, findings: state.findings, coverage: COVERAGE })
    // Bounded native plugin storage; original JSONL remains the source of truth.
    const keys = (await $.store.keys()).filter(k => k.startsWith('audit:'))
    if (keys.length > 20) {
      const records = []
      for (const k of keys) records.push({ key: k, updated: (await $.store.get(k))?.updated || 0 })
      records.sort((a, b) => a.updated - b.updated)
      for (const record of records.slice(0, records.length - 20)) if (record.key !== key) await $.store.delete(record.key)
    }
}

export async function settleAudit($, state) {
    if (!state.options.audit) return
    // Finite waits let -p exit. Interactive mode also has a lifecycle-owned timer.
    for (let i = 0; i < 3; i++) { await $.clock.sleep(250); await auditPoll($, state) }
}

export async function showAudit($, state) {
    await auditPoll($, state)
    $.ui.log('Safeguard: ' + state.checked + ' recorded requests checked. Audit is AFTER SEND; unrecorded calls and compaction are not certified.')
    if (!state.options.audit) $.ui.log('Context audit is disabled in plugin configuration.')
    if (!state.checked) $.ui.log('No request has been verified yet. This is not a clean result.')
    for (const finding of state.findings.slice(-3)) {
      $.ui.log(finding.message)
      for (const detail of finding.findings || []) $.ui.log(formatFinding(detail))
    }
    for (const [path, value] of state.files) {
      $.ui.log('Trace: ' + path)
      if (value.trace.pendingBytes) $.ui.log('Audit still reading ' + value.trace.pendingBytes + ' bytes; coverage is incomplete.')
    }
    return {} // Display-only output, never model context.
}

export async function endAudit($, state) {
    if (state.timer) { state.timer.cancel(); state.timer = null }
    await auditPoll($, state)
    if (state.options.audit && !state.checked) await auditNote($, state, 'coverage_unknown', 'No recorded API request was verified in this session.')
    for (const [path, value] of state.files) {
      if (value.trace.pendingBytes) await auditNote($, state, 'coverage_unknown', 'The session ended before its large log was fully read; audit coverage is incomplete.', { file: path })
      const missing = value.trace.replay.order.filter(k => !value.trace.audited.has(k))
      if (missing.length) await auditNote($, state, 'incomplete_trace', 'Some request dependencies are missing or unsupported; those requests could not be audited.', { file: path })
    }
    try { await persistAudit($, state) } catch { /* Never print into the terminal. */ }
}
