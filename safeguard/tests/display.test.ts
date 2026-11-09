import { progressSnapshot, publishProgress, rowStatus } from '../hooks/progress.js'
import { expect, test } from 'claude-code/testing'
import { protectLiterals, restoreLiterals, translateDisplay, createDisplay, renderDisplay, drainDisplay, displayCommand, stopDisplay } from '../hooks/display.js'

const options = { translate_output:true, api_key:'fake', api_base:'https://example.invalid/v1', model:'test' }
function environment(answer='完成。') {
  const calls=[], timers=[], toasts=[]; let invalidations=0
  const api={
    http:{fetch:async (url,init)=>{calls.push(JSON.parse(init.body));return {ok:true,text:JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({text:answer})}}]})}}},
    clock:{after:(_,fn)=>{const job={fn,cancel(){job.canceled=true}};timers.push(job);return job},every:(_,fn)=>{const job={fn,cancel(){job.canceled=true}};timers.push(job);return job}},
    ui:{status:()=>{},open:async()=>{},close:async()=>{},invalidate:()=>{invalidations++},toast:text=>toasts.push(text),resolve:()=>({Box:props=>({type:'Box',props}),Text:props=>({type:'Text',props})})}
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
  expect((await renderDisplay(env.api,state,original,next)).props.children[1]).toBe(original)
  expect(env.calls.length).toBe(0)
  state.active=false
  await drainDisplay(env.api,state)
  const shown=(await renderDisplay(env.api,state,original,next)).props.children[1]
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
  expect((await renderDisplay(env.api,state,event('New text.'),next)).props.children[1].props.text).toBe('New text.')
})

test('failed translation keeps original and is retried only on explicit retry',async()=>{
  const env=environment(),state=createDisplay(options)
  let calls=0;env.api.http.fetch=async()=>{calls++;return {ok:false}}
  await renderDisplay(env.api,state,event('Text.'),next);await drainDisplay(env.api,state)
  expect((await renderDisplay(env.api,state,event('Text.'),next)).props.children[1].props.text).toBe('Text.')
  await drainDisplay(env.api,state);expect(calls).toBe(1);expect(rowStatus(state,state.rows.get('row')).text).toContain('翻译失败')
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


test('progress reports real completed counts, current block and failure without fake percentages',async()=>{
  const env=environment(),state=createDisplay(options)
  state.active=true
  await renderDisplay(env.api,state,event('First block.','a'),next)
  await renderDisplay(env.api,state,event('Second block.','b'),next)
  expect(progressSnapshot(state).queued).toBe(2)
  expect(progressSnapshot(state).text).toContain('等待回答结束')
  state.active=false
  let release
  env.api.http.fetch=async()=>new Promise(resolve=>{release=()=>resolve({ok:false})})
  const job=drainDisplay(env.api,state)
  const progress=progressSnapshot(state,state.current.startedAt+4000)
  expect(progress.text).toContain('翻译中 #1 · 4s')
  expect(progress.text).toContain('0/2')
  expect(progress.text).toContain('First block.')
  await publishProgress(env.api,state)
  const timer=state.progressTimer
  await publishProgress(env.api,state)
  expect(state.progressTimer).toBe(timer)
  release();await job
  expect(progressSnapshot(state).failed).toBe(1)
  expect(progressSnapshot(state).text).toContain('1/2')
  await displayCommand(env.api,state,{args:'original'})
  expect(timer.canceled).toBe(true)
  expect(state.progressTimer).toBe(null)
})


test('finished progress closes once and does not restart a progress timer',async()=>{
  const env=environment(),state=createDisplay(options)
  let opened=0,closed=0
  env.api.ui.open=async()=>{opened++}
  env.api.ui.close=async()=>{closed++}
  state.active=true
  await renderDisplay(env.api,state,event('One answer.'),next)
  await publishProgress(env.api,state)
  await publishProgress(env.api,state)
  expect(opened).toBe(1)
  state.active=false
  await drainDisplay(env.api,state)
  await publishProgress(env.api,state)
  expect(state.progressTimer).toBe(null)
  expect(progressSnapshot(state).text).toContain('1/1')
  const close=state.progressClose
  await close.fn()
  expect(closed).toBe(1)
  expect(state.progressPane).toBe(false)
  expect(state.progressTimer).toBe(null)
  await publishProgress(env.api,state)
  expect(opened).toBe(1)
  expect(state.progressClose).toBe(null)
})
