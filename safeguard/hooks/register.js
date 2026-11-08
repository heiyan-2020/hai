import { translate } from './translate.js'
import { createAudit, auditStart, registerTrace, settleAudit, showAudit, endAudit } from './audit.js'
import { HAN } from './common.js'

export function register(on, configured) {
  const options = { api_base: 'https://api.deepseek.com', model: 'deepseek-flash', audit: true, ...configured }
  const audit = createAudit(options)
  on('session.start', async ($, e, next) => {
    await auditStart($, audit, e)
    await $.command.register({ name: 'safeguard-audit', description: 'Show local after-send audit findings; nothing is sent to the model.' })
    if (!options.api_key && !options.api_key_file) $.ui.toast('Configure the Safeguard translation API key in /plugin. Submitted prompts are blocked until configured.')
    return next(e)
  })
  on('classic.SessionStart', async ($, e, next) => {
    registerTrace(audit, e.transcript_path, e.cwd)
    return next(e)
  })
  on('classic.UserPromptSubmit', async ($, e, next) => {
    registerTrace(audit, e.transcript_path, e.cwd)
    if (typeof e.prompt === 'string' && HAN.test(e.prompt)) {
      return { decision: 'block', reason: 'Safeguard: Chinese remained after input translation. Nothing was submitted.',
        hookSpecificOutput: { hookEventName: 'UserPromptSubmit', suppressOriginalPrompt: true } }
    }
    return next(e)
  })
  on('prompt.submit', async ($, e, next) => {
    if (e.attachments && e.attachments.length) return { drop: 'Safeguard currently accepts text only.' }
    const text = await translate($, e.text, options)
    if (next.signal.aborted) return { drop: 'Submission canceled.' }
    return next({ ...e, text })
  }).catch(async ($, e, next) => {
    if (next.called) return next(e)
    return { drop: 'Safeguard translation failed or is not configured. Nothing was submitted. Check plugin configuration and retry.' }
  })
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    try { await settleAudit($, audit) } catch { /* UI/audit failures never rewrite a model response. */ }
    return result
  })
  on('session.end', async ($, e, next) => {
    try { await endAudit($, audit) } catch { /* No direct terminal output. */ }
    return next(e)
  })
  on('command.run', { command: 'safeguard-audit' }, async ($) => showAudit($, audit))
}
