import { expect, test } from 'claude-code/testing'
import { requestParameters, parseTranslation, requestTranslation, failureInfo, TranslationFailure } from '../hooks/provider.js'
import { translate } from '../hooks/translate.js'
import { translateDisplay } from '../hooks/display.js'

const response=(reason='stop',content='{"text":"译文"}')=>({ok:true,text:JSON.stringify({choices:[{finish_reason:reason,message:{content}}]})})

test('DeepSeek requests disable thinking and use a configurable larger generation limit',()=>{
  const defaults=requestParameters({})
  expect(defaults.max_tokens).toBe(32768)
  expect(defaults.thinking).toEqual({type:'disabled'})
  expect(defaults.reasoning_effort).toBe('none')
  expect(requestParameters({max_output_tokens:65536}).max_tokens).toBe(65536)
  expect(requestParameters({model:'other-model'}).thinking).toBe(undefined)
  expect(requestParameters({disable_thinking:false}).thinking).toBe(undefined)
  for (const bad of [0,8192.5,131073,'32768']) expect(()=>requestParameters({max_output_tokens:bad})).toThrow('configuration')
})

test('truncation is diagnosed before JSON parsing and includes the actual budget',()=>{
  try { parseTranslation(response('length','{"text":"unfinished'),65536);throw new Error('expected failure') }
  catch(error) {
    expect(failureInfo(error)).toEqual({code:'truncated',summary:'输出被截断，达到 token 上限（65536）',limit:65536})
  }
})

test('provider failures expose safe categories without provider content or keys',async()=>{
  try { parseTranslation({ok:false,status:429,text:'Bearer secret-provider-body'},32768) }
  catch(error) { expect(failureInfo(error)).toEqual({code:'http',summary:'翻译接口报错（HTTP 429）',status:429}) }
  for (const [content,code] of [['','empty'],['   ','empty'],['not json','json'],['{}','json']]) {
    try {parseTranslation(response('stop',content),32768);throw new Error('expected failure')}
    catch(error){expect(failureInfo(error).code).toBe(code)}
  }
  const api={http:{fetch:async()=>{throw new Error('request timeout Authorization: Bearer secret')}}}
  try {await requestTranslation(api,{api_key:'fake'},[]);throw new Error('expected failure')}
  catch(error){expect(failureInfo(error)).toEqual({code:'timeout',summary:'翻译请求超时'})}
  expect(JSON.stringify(failureInfo(new Error('sk-secret-value')))).not.toContain('sk-secret-value')
})

test('both input and assistant translation use the same request policy',async()=>{
  const calls=[]
  const api={http:{fetch:async(url,init)=>{
    calls.push(JSON.parse(init.body))
    return calls.length===1?response('stop','{"text":"hello","is_english":true}'):response('stop','{"text":"你好"}')
  }}}
  const options={model:'deepseek-flash',api_key:'fake',max_output_tokens:65536}
  expect(await translate(api,'你好',options)).toBe('hello')
  expect(await translateDisplay(api,'hello',options)).toBe('你好')
  for (const request of calls) {
    expect(request.max_tokens).toBe(65536)
    expect(request.thinking.type).toBe('disabled')
    expect(request.reasoning_effort).toBe('none')
  }
})
