"""Development-only test harness. Plugin runtime uses no Python."""
import json,os,shutil,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

requests=[];translations=[];mode='good'
class Mock(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if self.path=='/v1/chat/completions':
   translations.append(p)
   if mode=='fail':self.send_response(503);self.end_headers();return
   text=p['messages'][-1]['content'];out='Reply with OK only.' if any('\u3400'<=c<='\u9fff' for c in text) else text
   result={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'text':out,'is_english':True})}}]}
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result).encode());return
  requests.append(p)
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  msg={'id':'msg_'+uuid.uuid4().hex,'type':'message','role':'assistant','model':p['model'],'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}
  events=[{'type':'message_start','message':msg},{'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}},{'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':'OK'}},{'type':'content_block_stop','index':0},{'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':1}},{'type':'message_stop'}]
  for e in events:self.wfile.write(('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n').encode());self.wfile.flush()

def main():
 global mode
 cli=shutil.which('claude');assert cli
 plugin=str(Path(sys.argv[1]).resolve())
 server=ThreadingHTTPServer(('127.0.0.1',0),Mock);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='safeguard-plugin-e2e-') as temp:
   root=Path(temp);cc=root/'claude';cc.mkdir();base='http://127.0.0.1:'+str(server.server_port)
   env={k:v for k,v in os.environ.items() if not k.startswith(('ANTHROPIC_','CLAUDE_','HC_'))}
   env.update(HOME=str(root),CLAUDE_CONFIG_DIR=str(cc),ANTHROPIC_API_KEY='fake-anthropic-key',ANTHROPIC_BASE_URL=base,CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',NO_PROXY='127.0.0.1,localhost')
   marketplace=str(Path(plugin).parent)
   marketname=json.loads((Path(marketplace)/'.claude-plugin/marketplace.json').read_text())['name']
   installed=subprocess.run([cli,'plugin','install','safeguard','--marketplace',marketplace,'--json'],cwd=root,env=env,capture_output=True,text=True,timeout=80)
   assert installed.returncode==0,installed.stdout+installed.stderr
   keyfile=root/'translation-key';keyfile.write_text('fake-translation-key');keyfile.chmod(0o600)
   configured=subprocess.run([cli,'plugin','configure','safeguard@'+marketname,'--values-stdin'],input=json.dumps({'api_base':base+'/v1','model':'fake','api_key_file':str(keyfile),'audit':'true'}),cwd=root,env=env,capture_output=True,text=True,timeout=30)
   assert configured.returncode==0,configured.stdout+configured.stderr
   prefix=[cli,'-p','--model','claude-opus-5-5','--tools','']
   for case,system,prompt,sent in [('translate','English system.','请只回答 OK',True),('audit','English system.','hello',True),('fail','English system.','请只回答 OK',False)]:
    mode='fail' if case=='fail' else 'good';before=len(requests);sid=str(uuid.uuid4())
    if case=='audit':
     skill=cc/'skills/lesson/SKILL.md';skill.parent.mkdir(parents=True);skill.write_text('---\nname: lesson\ndescription: Learn with a paper: 用这篇论文训练我 and explain your reasoning.\n---\nTeach through exercises.\n')
    p=subprocess.run(prefix+(['--tools','Skill'] if case=='audit' else [])+['--session-id',sid,'--system-prompt',system,prompt],cwd=root,env=env,capture_output=True,text=True,timeout=80)
    print(json.dumps({'case':case,'sent':len(requests)-before,'exit':p.returncode,'stdout':p.stdout[-1800:],'stderr':p.stderr[-1800:]},ensure_ascii=False),flush=True)
    assert (len(requests)>before)==sent,case
    if sent:
     assert p.returncode==0 and 'OK' in p.stdout
     assert not any('\u3400'<=c<='\u9fff' for c in json.dumps(requests[-1]['messages'][0],ensure_ascii=False))
    if case=='audit':
     trace=next((cc/'projects').rglob(sid+'.jsonl'))
     padding=json.dumps({'type':'safeguard-test-padding','text':'English padding. '*170000})+'\n'
     trace.write_text(padding+trace.read_text())
     assert trace.stat().st_size>2*1024*1024
     mode='good';count=len(requests)
     detail=subprocess.run(prefix+['--output-format','stream-json','--verbose','--resume',sid,'/safeguard-audit'],cwd=root,env=env,capture_output=True,text=True,timeout=80)
     print(json.dumps({'case':'audit-command','sent':len(requests)-count,'details_verified':'ALREADY BEEN SENT' in detail.stdout,'source_verified':str(skill)+':3' in detail.stdout,'stderr':detail.stderr[-1000:]},ensure_ascii=False),flush=True)
     assert len(requests)==count,'Details command triggered a model request'
     assert 'ALREADY BEEN SENT' in detail.stdout+detail.stderr,'Audit detail missing'
     assert str(skill)+':3' in detail.stdout+detail.stderr,'Skill source not identified'
   print('Installed native plugin integration passed, including large-log OS reads; no --plugin-dir, launcher or SG environment variables used.',flush=True)
 finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
