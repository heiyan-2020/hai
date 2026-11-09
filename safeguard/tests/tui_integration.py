"""Real terminal integration test. Development dependencies: Python 3 and pyte; POSIX only."""
import fcntl,json,os,pty,re,select,shutil,signal,struct,subprocess,sys,tempfile,termios,threading,time,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pyte
artifacts=Path(tempfile.mkdtemp(prefix='sg-display-artifacts-'))
columns=int(os.environ.get('SG_TEST_COLUMNS','160'))
screen=pyte.Screen(columns,45);stream=pyte.ByteStream(screen)
def shown():return '\n'.join(screen.display)
SOURCE='The check is complete.\n\nRun `printf hello`.\n\n```sh\nprintf hello\n```'
requests=[];translations=[];failures=0
class Mock(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  global failures
  p=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if self.path.endswith('/chat/completions'):
   translations.append(p);text=p['messages'][-1]['content']
   display='Simplified Chinese' in p['messages'][0]['content']
   if display:
    time.sleep(4)
    if not failures:
     failures+=1;self.send_response(503);self.end_headers();return
   value={'text':text.replace('The check is complete.','检查已完成。').replace('Run ','运行 ') if display else text,'is_english':True}
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}).encode());return
  requests.append(p);self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  message={'id':'msg_'+uuid.uuid4().hex,'type':'message','role':'assistant','model':p['model'],'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}
  events=[{'type':'message_start','message':message},{'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}},{'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':SOURCE}},{'type':'content_block_stop','index':0},{'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':30}},{'type':'message_stop'}]
  for e in events:self.wfile.write(('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n').encode());self.wfile.flush()
server=ThreadingHTTPServer(('127.0.0.1',0),Mock);threading.Thread(target=server.serve_forever,daemon=True).start()
root=Path(tempfile.mkdtemp(prefix='sg-display-tui-')).resolve();cc=root/'.claude';cc.mkdir()
(cc/'.claude.json').write_text(json.dumps({'hasCompletedOnboarding':True,'customApiKeyResponses':{'approved':['fake-key']},'theme':'dark','projects':{str(root):{'hasTrustDialogAccepted':True}}}))
(root/'.claude.json').write_text((cc/'.claude.json').read_text())
base='http://127.0.0.1:'+str(server.server_port)
env={k:v for k,v in os.environ.items() if not k.startswith(('ANTHROPIC_','CLAUDE_','HC_'))}
env.update(HOME=str(root),CLAUDE_CONFIG_DIR=str(cc),ANTHROPIC_BASE_URL=base,ANTHROPIC_AUTH_TOKEN='fake-key',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',TERM='xterm-256color',NO_PROXY='127.0.0.1,localhost')
settings={'pluginConfigs':{'safeguard':{'options':{'api_base':base+'/v1','api_key':'fake','model':'fake','audit':False,'translate_output':True}}}}
cli=shutil.which('claude');sid=str(uuid.uuid4());plugin=str(Path(sys.argv[1]).resolve())
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',45,columns,0,0))
p=subprocess.Popen([cli,'--plugin-dir',plugin,'--settings',json.dumps(settings),'--model','claude-opus-5-5','--tools','','--system-prompt','English system.','--session-id',sid,'hello'],stdin=slave,stdout=slave,stderr=slave,cwd=root,env=env,start_new_session=True);os.close(slave)
buffer=b'';allout=b'';saw_english=False
def until(predicate,timeout=40):
 global buffer,allout,saw_english
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  if predicate():return
  if p.poll() is not None:raise RuntimeError('CLI exited '+str(p.returncode))
  if select.select([master],[],[],.2)[0]:
   data=os.read(master,65536);buffer+=data;allout+=data;stream.feed(data)
   (artifacts/'display-tui-screen.txt').write_text(shown())
   saw_english = saw_english or 'The check is complete.' in shown()
   if b'\x1b[6n' in data:os.write(master,b'\x1b[1;1R')
   if b'\x1b[c' in data:os.write(master,b'\x1b[?1;2c')
   text=buffer.decode(errors='replace')
   compact=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text).replace(' ','').replace('\n','').replace('\r','')
   (artifacts/'display-tui-screen.log').write_bytes(allout)
   if 'DoyouwanttousethisAPIkey?' in compact:
    os.write(master,b'\x1b[A\r');buffer=b'';continue
   if 'Yes,Itrustthisfolder' in compact:
    os.write(master,b'\x1b[B\r');buffer=b'';continue
   if 'trust this folder' in text or 'trust the files' in text:
    os.write(master,b'\r');buffer=b''
   if 'Yes, I approve' in text and 'API key' in text:
    os.write(master,b'\r');buffer=b''
 raise TimeoutError('Timed out')
try:
 until(lambda:'翻译中 #1' in shown() and '2s' in shown(),65)
 progress_rows=[(i,line) for i,line in enumerate(screen.display) if '翻译中 #1' in line]
 assert len(progress_rows)==1,'Progress UI stacked instead of updating'
 if columns>=144:
  assert progress_rows[0][0]<10 and progress_rows[0][1].find('翻译中')>columns//2,'Progress not at upper right'
 assert '0/1' in shown() and '正在翻译 #1' in shown(),'Progress or block marker absent'
 (artifacts/'progress-running.txt').write_text(shown())
 until(lambda:'HTTP 503' in shown(),65)
 assert 'The check is complete.' in shown() and len(requests)==1
 (artifacts/'failure-readable.txt').write_text(shown())
 os.write(master,b'/safeguard-display retry\r')
 until(lambda:'检查已完成' in shown(),65)
 assert '已翻译 #1' in shown(),'Translated block marker absent'
 assert 'printf hello' in shown(),'Code rendering changed'
 (artifacts/'display-tui-chinese.txt').write_text(shown())
 assert saw_english,'Original stream not shown'
 display=[r for r in translations if 'Simplified Chinese' in r['messages'][0]['content']]
 assert len(display)==2,len(display)
 assert 'printf hello' not in display[0]['messages'][1]['content']
 buffer=b'';os.write(master,b'/safeguard-display original\r')
 until(lambda:'The check is complete.' in shown(),15)
 assert len(requests)==1,'Display command sent a model message'
 buffer=b'';os.write(master,b'/safeguard-display zh\r')
 until(lambda:'检查已完成' in shown(),15)
 assert len([r for r in translations if 'Simplified Chinese' in r['messages'][0]['content']])==2
 buffer=b'';os.write(master,b'continue\r');until(lambda:len(requests)>=2,30)
 history=json.dumps(requests[-1]['messages'],ensure_ascii=False)
 assert SOURCE in [b.get('text') for m in requests[-1]['messages'] if m['role']=='assistant' for b in m['content'] if isinstance(b,dict)]
 assert '检查已完成' not in history,'Translated display contaminated model history'
 time.sleep(2)
 traces=list((cc/'projects').rglob(sid+'.jsonl'));assert traces
 records=[json.loads(x) for x in traces[0].read_text().splitlines()]
 assistant=[r for r in records if r.get('type')=='assistant']
 assert assistant and '检查已完成' not in json.dumps(assistant,ensure_ascii=False)
 print(json.dumps({'readable_HTTP_failure_and_retry':True,'progress_single_live_panel':True,'columns':columns,'tui_chinese_replacement':True,'original_toggle':True,'cache_reused':True,'protected_code_not_sent':True,'followup_history_english':True,'jsonl_assistant_original':True,'model_requests':len(requests)}),flush=True)
finally:
 try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5)
 except Exception:pass
 os.close(master);server.shutdown();server.server_close()
 (artifacts/'display-tui-screen.log').write_bytes(allout)
 print('Test fixture: '+str(root)+'; screen captures: '+str(artifacts),flush=True)
