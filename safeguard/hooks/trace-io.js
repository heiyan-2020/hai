import { Replay } from './replay.js'

const BLOCK = 262144
function decode64(text) { return Uint8Array.fromBase64(text.replace(/\s/g, '')) }

export async function readRange($, path, offset, size) {
  if (size <= 2 * 1024 * 1024) {
    const result = await $.fs.read(path, { as: 'bytes' })
    return decode64(result.base64).slice(offset)
  }
  // Native fs.read has a size ceiling. Built-in OS utilities read bounded byte
  // ranges for larger files; no Python/Node/runtime installation is needed.
  const windows = await $.env.get('OS') === 'Windows_NT'
  const block = Math.floor(offset / BLOCK)
  let result
  if (windows) {
    result = await $.process.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
      '$f=[IO.File]::Open($env:SG_TRACE_PATH,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite);try{[void]$f.Seek([long]$env:SG_TRACE_OFFSET,[IO.SeekOrigin]::Begin);$b=New-Object byte[] 262144;$n=$f.Read($b,0,$b.Length);[Console]::Write([Convert]::ToBase64String($b,0,$n))}finally{$f.Dispose()}'],
      { env: { SG_TRACE_PATH: path, SG_TRACE_OFFSET: String(block * BLOCK) }, timeoutMs: 10000 })
  } else {
    result = await $.process.run(['sh', '-c', 'dd if="$SG_TRACE_PATH" bs=262144 skip="$SG_TRACE_BLOCK" count=1 2>/dev/null | base64'],
      { env: { SG_TRACE_PATH: path, SG_TRACE_BLOCK: String(block) }, timeoutMs: 10000 })
  }
  if (result.exitCode !== 0 || result.isStdoutTruncated) throw new Error('Unable to read trace range')
  const bytes = decode64(result.stdout).slice(offset - block * BLOCK)
  if (!bytes.length && size > offset) throw new Error('Trace read failed or file changed')
  return bytes
}

export class TraceFile {
  constructor(path) {
    this.path = path; this.offset = 0; this.pending = ''; this.decoder = new TextDecoder('utf-8', { fatal: true })
    this.pendingBytes = 0; this.replay = new Replay(); this.audited = new Set(); this.warned = new Set()
  }

}

export async function readTrace($, trace) {
    if (!await $.fs.exists(trace.path)) return
    const stat = await $.fs.stat(trace.path)
    if (stat.size < trace.offset) throw new Error('Trace was truncated; reopen the session to restart reconstruction')
    let budget = 4 * 1024 * 1024
    while (trace.offset < stat.size && budget > 0) {
      const bytes = await readRange($, trace.path, trace.offset, stat.size)
      if (!bytes.length) break
      trace.offset += bytes.length; budget -= bytes.length
      trace.pending += trace.decoder.decode(bytes, { stream: true })
      if (trace.pending.length > 32 * 1024 * 1024) throw new Error('Trace record exceeds audit limit')
      let end
      while ((end = trace.pending.indexOf('\n')) >= 0) {
        const line = trace.pending.slice(0, end); trace.pending = trace.pending.slice(end + 1)
        if (!line.trim()) continue
        try { await trace.replay.feed(JSON.parse(line)) }
        catch { trace.replay.errors.push('Invalid record ending before byte ' + trace.offset) }
      }
    }
    trace.pendingBytes = Math.max(0, stat.size - trace.offset)
}
