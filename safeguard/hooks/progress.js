import { display } from './common.js'
export const PROGRESS_PANE = 'safeguard-translation-progress'

export function progressSnapshot(state, now = Date.now()) {
  const rows = new Map()
  for (const row of state.rows.values()) if (row.visible && row.text.trim()) rows.set(row.text, row)
  if (state.current) rows.set(state.current.text, state.current)
  let done = 0, failed = 0, queued = 0
  for (const row of rows.values()) {
    const cached = state.cache.get(row.text)
    if (cached?.status === 'done') done++
    else if (cached?.status === 'failed') failed++
    else if (!row.attempted && !cached) queued++
  }
  const total = rows.size, finished = done + failed
  const filled = total ? Math.floor(10 * finished / total) : 0
  const bar = '[' + '█'.repeat(filled) + '░'.repeat(10 - filled) + '] ' + finished + '/' + total
  const current = state.current
  const heading = current ? '翻译中 #' + current.number + ' · ' + Math.max(0, Math.floor((now - current.startedAt) / 1000)) + 's'
    : queued ? (state.active ? '等待回答结束' : '等待翻译')
    : failed ? '翻译结束 · ' + failed + ' 段失败，保留原文' : '翻译完成'
  const excerpt = current ? display(current.text).slice(0, 48) : ''
  return { total, done, failed, queued, current, running: Boolean(current || queued),
    text: heading + '\n' + bar + (excerpt ? '\n' + excerpt : '') }
}

export function stopProgress(state) {
  for (const key of ['progressTimer', 'progressRefresh', 'progressClose']) {
    if (state[key]) state[key].cancel()
    state[key] = null
  }
}

export async function hideProgress($, state) {
  stopProgress(state)
  $.ui.status(undefined)
  if (state.progressPane) await $.ui.close(PROGRESS_PANE)
  state.progressPane = false; state.progressPlaced = false
}

export async function publishProgress($, state) {
  if (state.closed || !state.enabled) { await hideProgress($, state); return }
  const progress = progressSnapshot(state)
  if (!progress.total) { await hideProgress($, state); state.lastProgress = null; return }
  const changed = state.lastProgress !== progress.text
  state.lastProgress = progress.text
  if (progress.running) {
    state.hadProgress = true
    if (state.progressClose) { state.progressClose.cancel(); state.progressClose = null }
    if (!state.progressTimer) state.progressTimer = $.clock.every(1000, async () => publishProgress($, state))
    if (!state.progressPane && !state.progressDismissed) {
      state.progressPane = true
      try { await $.ui.open({ id: PROGRESS_PANE, title: '翻译进度', rows: 5, columns: 36 }) }
      catch { state.progressPane = false }
    }
    // Native panes dock at the right in wide terminals. An automatic pane may
    // wait at narrow widths; the pinned status remains visible in that case.
    $.ui.status(state.progressPlaced ? undefined : progress.text.replace(/\n/g, ' · '))
  } else {
    if (state.progressTimer) state.progressTimer.cancel()
    state.progressTimer = null
    if (state.hadProgress && changed) {
      $.ui.status(state.progressPlaced ? undefined : progress.text.replace(/\n/g, ' · '))
      if (!state.progressClose) state.progressClose = $.clock.after(3000, async () => hideProgress($, state))
    }
  }
  if (changed) $.ui.invalidate('ui.render')
}

export function refreshProgress($, state) {
  if (state.progressRefresh || state.closed || !state.enabled) return
  const progress = progressSnapshot(state)
  if (!progress.total || progress.text === state.lastProgress) return
  state.progressRefresh = $.clock.after(0, async () => {
    state.progressRefresh = null
    await publishProgress($, state)
  })
}

export async function renderProgress($, state, e, next) {
  if (e.requestId !== PROGRESS_PANE || e.surface !== 'terminal') return next(e)
  state.progressPlaced = true
  $.ui.status(undefined)
  const { Box, Text } = $.ui.resolve(e)
  const progress = progressSnapshot(state)
  const lines = progress.text.split('\n')
  return Box({ flexDirection: 'column', children: [
    Text({ bold: true, children: ['翻译进度'] }),
    Text({ color: progress.running ? 'cyan' : progress.failed ? 'yellow' : 'green', children: [lines[0]] }),
    Text({ children: [lines[1]] }),
    ...(lines[2] ? [Text({ dimColor: true, children: [lines[2]] })] : []),
    Text({ dimColor: true, children: ['当前可见文本块 · 已处理/总数'] })
  ] })
}

export function rowStatus(state, row) {
  const cached = state.cache.get(row.text), id = '#' + row.number
  if (cached?.status === 'done') return { text: (cached.text === row.text ? '原文 · 无需翻译 ' : '已翻译 ') + id, color: 'green' }
  if (cached?.status === 'failed') return { text: '翻译失败 ' + id + ' · ' + (cached.error?.summary || '未分类错误') + ' · 保留原文 · /safeguard-display retry', color: 'yellow' }
  if (cached?.status === 'pending') return { text: '正在翻译 ' + id, color: 'cyan' }
  if (row.attempted) return { text: '原文 ' + id + ' · 译文缓存已释放', color: 'gray' }
  return { text: (state.active ? '等待回答结束 ' : '等待翻译 ') + id, color: 'gray' }
}
