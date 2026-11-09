const MESSAGES = {
  configuration: ['Translation configuration is invalid', '翻译配置无效'],
  missing_key: ['Translation key is not configured', '未配置翻译密钥'],
  timeout: ['Translation request timed out', '翻译请求超时'],
  network: ['Translation network request failed', '翻译网络请求失败'],
  canceled: ['Translation request was canceled', '翻译请求已取消'],
  http: ['Translation service returned an HTTP error', '翻译接口报错'],
  truncated: ['Incomplete translation: output token limit reached', '输出被截断，达到 token 上限'],
  response: ['Invalid translation service response', '接口响应格式异常'],
  json: ['Translation was not valid JSON', '译文不是有效 JSON'],
  empty: ['Translation was empty', '接口返回了空译文'],
  stop: ['Translation did not finish normally', '翻译未正常结束'],
  language: ['Translation failed the language check', '译文未通过语言检查'],
  literals: ['Translation changed protected literals', '译文改变了受保护的代码或链接'],
  size: ['Display text too large', '文本超过当前单块长度限制']
}

export class TranslationFailure extends Error {
  constructor(code, details = {}) {
    super(MESSAGES[code]?.[0] || 'Translation failed')
    this.name = 'TranslationFailure'; this.code = code; this.details = details
  }
}

export function failureInfo(error) {
  const code = error instanceof TranslationFailure && MESSAGES[error.code] ? error.code : 'unknown'
  const detail = code === 'unknown' ? {} : error.details
  const status = Number.isInteger(detail?.status) && detail.status >= 100 && detail.status <= 599 ? detail.status : null
  const limit = Number.isInteger(detail?.limit) ? detail.limit : null
  let summary = MESSAGES[code]?.[1] || '未分类错误'
  if (status) summary += '（HTTP ' + status + '）'
  if (code === 'truncated' && limit) summary += '（' + limit + '）'
  return { code, summary, ...(status ? { status } : {}), ...(limit ? { limit } : {}) }
}

export function requestParameters(options) {
  const model = options.model || 'deepseek-flash'
  const limit = options.max_output_tokens ?? 32768
  if (!Number.isInteger(limit) || limit < 256 || limit > 131072) throw new TranslationFailure('configuration')
  const params = { model, temperature: 0, max_tokens: limit, response_format: { type: 'json_object' } }
  if (options.disable_thinking !== false && /(^|\/)deepseek[-/]/i.test(model)) {
    params.thinking = { type: 'disabled' }
    params.reasoning_effort = 'none'
  }
  return params
}

export function parseTranslation(response, limit) {
  if (!response.ok) throw new TranslationFailure('http', { status: response.status })
  let body
  try { body = JSON.parse(response.text) } catch { throw new TranslationFailure('response') }
  const choice = body?.choices?.[0]
  if (!choice) throw new TranslationFailure('response')
  if (choice.finish_reason === 'length') throw new TranslationFailure('truncated', { limit })
  if (choice.finish_reason !== 'stop') throw new TranslationFailure('stop')
  const content = choice.message?.content
  if (typeof content !== 'string' || !content.trim()) throw new TranslationFailure('empty')
  let value
  try { value = JSON.parse(content) } catch { throw new TranslationFailure('json') }
  if (!value || typeof value.text !== 'string') throw new TranslationFailure('json')
  if (!value.text.trim()) throw new TranslationFailure('empty')
  return value
}

export async function requestTranslation($, options, messages) {
  const params = requestParameters(options)
  let key = options.api_key
  try { if (!key && options.api_key_file) key = (await $.fs.read(options.api_key_file)).trim() }
  catch { throw new TranslationFailure('missing_key') }
  if (typeof key !== 'string' || !key.trim()) throw new TranslationFailure('missing_key')
  let url
  try { url = new URL(options.api_base || 'https://api.deepseek.com') }
  catch { throw new TranslationFailure('configuration') }
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new TranslationFailure('configuration')
  let response
  try {
    response = await $.http.fetch(url.href.replace(/\/$/, '') + '/chat/completions', {
      method: 'POST', headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...params, messages })
    })
  } catch (error) {
    const message = String(error?.message || '')
    // Classify locally; never expose provider error text, request bodies or headers.
    throw new TranslationFailure(/timed?\s*out|timeout|deadline/i.test(message) ? 'timeout' : /abort|cancel/i.test(message) ? 'canceled' : 'network')
  }
  return parseTranslation(response, params.max_tokens)
}
