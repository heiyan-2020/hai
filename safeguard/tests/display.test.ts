import { expect, test } from 'claude-code/testing'
import { protectLiterals, restoreLiterals, translateDisplay, createDisplay, renderDisplay, drainDisplay, displayCommand, stopDisplay } from '../hooks/display.js'

const options = { translate_output:true, api_key:'fake', api_base:'https://example.invalid/v1', model:'test' }
function environment(answer='完成。') {
  const calls=[], timers=[], toasts=[]; let invalidations=0
  const api={
    http:{fetch:async (url,init)=>{calls.push(JSON.parse(init.body));return {ok:true,text:JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({text:answer})}}]})}}},
    clock:{after:(_,fn)=>{const job={fn,cancel(){job.canceled=true}};timers.push(job);return job}},
    ui:{invalidate:()=>{invalidations++},toast:text=>toasts.push(text)}
  }
  return {api,calls,timers,toasts,invalidations:()=>invalidations}
}
const event=(text,id='row')=>({surface:'terminal',component:'AssistantMessage',requestId:id,props:{text,isFirstOfReply:true,onScreen:{first:0,last:2}}})
const next=async e=>e

test('display translation protects fenced, inline and link literals exactly',async()=>{
  const original='Run ``a`b`` and `x()`; see [guide](https://example.org/a).\n~~~~py\nprint("English")\n~~~\n~~~~\nThen finish.'
  const protectedText=protectLiterals(original)
  expect(protectedText.masked).not.toContain('print(')
  expect(protectedText.masked).not.toContain('https://')
  expect(restoreLiterals(protectedText.masked,protectedText)).toBe(original)
  expect(()=>restoreLiterals(protectedText.masked.replace(protectedText.tokens[0],''),protectedText)).toThrow('literals')
  const unfinished='Explanation\n```sh\necho English'
  expect(restoreLiterals(protectLiterals(unfinished).masked,protectLiterals(unfinished))).toBe(unfinished)
})

test('streaming stays original, then only render props change and duplicate renders reuse cache',async()=>{
  const env=environment(),state=createDisplay(options)
  state.active=true
  const original=Object.freeze(event('All done.'));Object.freeze(original.props)
  expect(await renderDisplay(env.api,state,original,next)).toBe(original)
  expect(env.timers.length).toBe(0)
  state.active=false
  await drainDisplay(env.api,state)
  const shown=await renderDisplay(env.api,state,original,next)
  expect(shown.props.text).toBe('完成。')
  expect(original.props.text).toBe('All done.')
  expect(shown.props.onScreen).toBe(original.props.onScreen)
  await renderDisplay(env.api,state,original,next);await drainDisplay(env.api,state)
  expect(env.calls.length).toBe(1)
})

test('a late translation never replaces different text in the same row',async()=>{
  const env=environment(),state=createDisplay(options)
  let release
  env.api.http.fetch=async()=>new Promise(resolve=>{release=()=>resolve({ok:true,text:JSON.stringify({choices:[{finish_reason:'stop',message:{content:'{"text":"旧文本。"}'}}]})})})
  await renderDisplay(env.api,state,event('Old text.'),next)
  const job=drainDisplay(env.api,state)
  state.active=true
  await renderDisplay(env.api,state,event('New text.'),next)
  release();await job
  expect((await renderDisplay(env.api,state,event('New text.'),next)).props.text).toBe('New text.')
})

test('failed translation keeps original and is retried only on explicit retry',async()=>{
  const env=environment(),state=createDisplay(options)
  let calls=0;env.api.http.fetch=async()=>{calls++;return {ok:false}}
  await renderDisplay(env.api,state,event('Text.'),next);await drainDisplay(env.api,state)
  expect((await renderDisplay(env.api,state,event('Text.'),next)).props.text).toBe('Text.')
  await drainDisplay(env.api,state);expect(calls).toBe(1);expect(env.toasts.length).toBe(1)
  await displayCommand(env.api,state,{args:'retry'});await drainDisplay(env.api,state)
  expect(calls).toBe(2)
})

test('original mode, nonterminal surfaces and closed sessions do not translate',async()=>{
  const env=environment(),state=createDisplay(options)
  await displayCommand(env.api,state,{args:'original'})
  const e=event('English.');expect(await renderDisplay(env.api,state,e,next)).toBe(e)
  await displayCommand(env.api,state,{args:'zh'})
  expect(await renderDisplay(env.api,state,{...e,surface:'vscode'},next)).toEqual({...e,surface:'vscode'})
  stopDisplay(state);await drainDisplay(env.api,state);expect(env.calls.length).toBe(0)
})

test('output request contains masked prose and rejects truncated or damaged translations',async()=>{
  const env=environment('中文。 SG_LITERAL_0_END')
  const source='Explain `secret_code()`'
  expect(await translateDisplay(env.api,source,options)).toBe('中文。 `secret_code()`')
  expect(env.calls[0].messages[1].content).not.toContain('secret_code')
  env.api.http.fetch=async()=>({ok:true,text:JSON.stringify({choices:[{finish_reason:'length',message:{content:'{"text":"部分。"}'}}]})})
  await expect(translateDisplay(env.api,source,options)).rejects.toThrow('Incomplete')
  expect(await translateDisplay(env.api,'```sh\necho hello\n```',options)).toBe('```sh\necho hello\n```')
})
