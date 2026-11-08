export const HAN = /[\u2e80-\u2fff\u3005\u3007\u3021-\u3029\u3038-\u303b\u31c0-\u31ef\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u{20000}-\u{2ffff}\u{30000}-\u{323af}]/u
export const COVERAGE = {
  phase: 'after_send', scope: 'recorded_api_requests_only',
  omitted: ['client attribution block', 'metadata', 'stream', 'HTTP headers'],
  knownGaps: ['Compaction model requests were unrecorded in the tested CLI.']
}
export function stable(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']'
  return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + stable(value[k])).join(',') + '}'
}
export async function hash(value) {
  const bytes = new TextEncoder().encode(stable(value))
  const result = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(result), v => v.toString(16).padStart(2, '0')).join('')
}
export function clone(value) { return JSON.parse(JSON.stringify(value)) }
export function* strings(value, path = '$', depth = 0) {
  if (depth > 80) throw new Error('Context nesting exceeds audit limit')
  if (typeof value === 'string') yield [path, value]
  else if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) yield* strings(value[i], path + '[' + i + ']', depth + 1)
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      yield [path + '.<key>', key]
      const label = /^[A-Za-z_][A-Za-z0-9_]{0,47}$/.test(key) ? '.' + key : '[field]'
      yield* strings(child, path + label, depth + 1)
    }
  }
}
export function display(text) {
  return text.replace(/[\p{Cc}\p{Cf}]/gu, ' ')
    .replace(/\b(?:sk|sk-ant)-[A-Za-z0-9_-]{8,}/gi, '[REDACTED]')
    .replace(/\bBearer\s+\S+/gi, 'Bearer [REDACTED]')
    .replace(/((?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*)[^\s,;]+/gi, '$1[REDACTED]')
    .replace(/\s+/g, ' ').trim()
}
export function excerpt(text) {
  text = display(text)
  const position = text.search(HAN)
  const start = Math.max(0, position - 45), end = Math.min(text.length, position + 115)
  return (start ? '...' : '') + text.slice(start, end) + (end < text.length ? '...' : '')
}
export function enforceRules(rules, value, scope) {
  for (const rule of rules) {
    if (!rule || rule.type !== 'deny_pattern' || !['all','prompt','context'].includes(rule.scope || 'all') || typeof rule.pattern !== 'string') throw new Error('Invalid safeguard rule')
    let pattern = rule.pattern, flags = rule.flags || ''
    const inline = /^\(\?([ims]+)\)/.exec(pattern)
    if (inline) { pattern = pattern.slice(inline[0].length); flags += inline[1] }
    if (!/^[imsu]*$/.test(flags)) throw new Error('Unsupported rule flags')
    const regex = new RegExp(pattern, [...new Set(flags)].join(''))
    if ((rule.scope || 'all') !== 'all' && rule.scope !== scope) continue
    for (const [, text] of strings(value)) if (regex.test(text)) throw new Error('A configured safeguard rule matched')
  }
}
export async function readRules($, options) {
  if (!options.rules_file) return []
  const data = JSON.parse(await $.fs.read(options.rules_file))
  const rules = Array.isArray(data) ? data : data.rules
  if (!Array.isArray(rules)) throw new Error('Rules must be an array')
  return rules
}
