import { expect, test } from 'claude-code/testing'
import { Replay } from '../hooks/replay.js'
import { hash, enforceRules } from '../hooks/common.js'

async function sample() {
  const shape={system:[{type:'text',text:'English system.'}],tools:[]}
  const message={role:'user',content:[{type:'text',text:'hello'}]}
  const body={model:'test',...shape,messages:[message]}
  const request={type:'api-request',sessionId:'s',id:'r',shapeHash:await hash(shape),params:{model:'test'},keep:0,tail:[await hash(message)],cacheControl:[],requestDigest:await hash(body)}
  return {shape,message,body,request}
}

test('unconfigured plugin fails closed at prompt submission', async ($) => {
  const result=await $.prompt.submit({text:'hello',asUser:true})
  expect(result.drop).toContain('not configured')
})

test('trace reconstructs normal-message references and verifies digest', async () => {
  const f=await sample(),replay=new Replay()
  await replay.feed({type:'api-request-shape',sessionId:'s',shapeHash:await hash(f.shape),shape:f.shape})
  await replay.feed({type:'user',sessionId:'s',message:{role:'user',content:'hello'}})
  await replay.feed(f.request)
  expect((await replay.reconstruct('s\0r')).request).toEqual(f.body)
  replay.requests.get('s\0r').requestDigest='corrupt'
  await expect(replay.reconstruct('s\0r')).rejects.toThrow('digest')
})

test('missing blocks and cyclic deltas are not guessed', async () => {
  const f=await sample(),r=new Replay()
  await r.feed({type:'api-request-shape',sessionId:'s',shapeHash:await hash(f.shape),shape:f.shape})
  await r.feed(f.request)
  await expect(r.reconstruct('s\0r')).rejects.toThrow('Missing message')
  r.requests.get('s\0r').base='r'
  await expect(r.reconstruct('s\0r')).rejects.toThrow('Cyclic')
})

test('cache overlays do not mutate base messages or nested business data', async () => {
  const f=await sample(),r=new Replay()
  const msg={role:'assistant',content:[{type:'tool_use',name:'x',id:'t',input:{cache_control:'keep me'}}]}
  const body={...f.body,messages:[{...msg,cache_control:{type:'ephemeral'}}]}
  await r.feed({type:'api-request-shape',sessionId:'s',shapeHash:await hash(f.shape),shape:f.shape})
  const h=await hash(msg)
  await r.feed({type:'api-request-blob',sessionId:'s',hash:h,message:msg})
  await r.feed({...f.request,tail:[h],cacheControl:[{path:['messages',0],value:{type:'ephemeral'}}],requestDigest:await hash(body)})
  expect((await r.reconstruct('s\0r')).request).toEqual(body)
  expect(r.blobs.get('s\0'+h).cache_control).toBe(undefined)
  expect(r.blobs.get('s\0'+h).content[0].input.cache_control).toBe('keep me')
})

test('custom rules support scope and common inline flags', () => {
  const rules=[{type:'deny_pattern',scope:'prompt',pattern:'(?i)secret'}]
  expect(()=>enforceRules(rules,'SECRET','prompt')).toThrow()
  enforceRules(rules,'SECRET','context')
})
