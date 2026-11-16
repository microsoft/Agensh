"""Fixed-policy OPS ports for an authorized same-owner natural-stop driver.
SELECT-only native queue metadata; fixed template POST in original task channel.
No task/candidate/session/error/model body reads, retries, or event mutation.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import datetime,hashlib,json,os,re,subprocess
POLICY=Path((_C14_SCRATCH + '/ag27s16/d/policy/r16-natural-stop-neutral-v1/POLICY.json'))
POLICY_SHA='5dddb69c9be2ae5ffd026cba1b15c53cf0cd458734820b8406d020762b13b7d1'
TEMPLATE_SHA='55fa7e2fa748fc2492467400e34dca28e3e2d30afdcd81c38cd86c7fca30aac2'
SQL="START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;\nSELECT state,attempts,COUNT(*) AS event_count FROM events GROUP BY state,attempts ORDER BY state,attempts;\nROLLBACK;\n"
DOCKER=('/usr/bin/docker','--host','unix:///var/run/docker.sock')
def require(ok,code):
 if not ok:raise ValueError(code)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def policy():
 b=POLICY.read_bytes();require(hashlib.sha256(b).hexdigest()==POLICY_SHA,'NATURAL_POLICY_SHA')
 p=json.loads(b);t=p['message']['template_utf8'];require(hashlib.sha256(t.encode()).hexdigest()==TEMPLATE_SHA,'NATURAL_TEMPLATE_SHA')
 return p

def _original_host(driver):
 h=driver.host
 # The installed AttemptHost keeps original methods/state and routes a2 only.
 return h.original if hasattr(h,'original') else h

def _record(driver,t):
 p=policy();require(type(t)is str and t in {r['trajectory']for r in p['tracks']},'NATURAL_AUTHORIZED_TRACK')
 h=_original_host(driver);r=h.STATE[t]
 require(r['row']['trajectory_id']==t,'NATURAL_EXACT_REGISTERED_TRACK')
 return h,r,p

def parse_queue(raw):
 lines=raw.decode('ascii','strict').splitlines()
 require(bool(lines)and lines[0]=='state\tattempts\tevent_count','NATURAL_QUEUE_HEADER')
 rows=[];counts={s:0 for s in('pending','sending','retrying','sent','failed')}
 for l in lines[1:]:
  a=l.split('\t');require(len(a)==3 and a[0]in counts,'NATURAL_QUEUE_COLUMNS')
  require(a[1].isdigit()and a[2].isdigit(),'NATURAL_QUEUE_INTEGERS')
  attempts,count=int(a[1]),int(a[2]);counts[a[0]]+=count
  rows.append({'state':a[0],'attempts':attempts,'count':count})
 return {'counts':counts,'rows':rows,'queue_idle':all(counts[s]==0 for s in('pending','sending','retrying'))}

def queue_metadata(driver,trajectory):
 _,r,_=_record(driver,trajectory)
 ms=[v for v in r['backend_proof']['backend_services']if v['service']=='mysql']
 require(len(ms)==1 and re.fullmatch('[a-f0-9]{64}',ms[0]['id']),'NATURAL_REGISTERED_MYSQL_ID')
 args=[*DOCKER,'exec','-i',ms[0]['id'],'sh','-c','export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --batch --raw --user=root --connect-timeout=5 --database=omcgitea']
 try:
  q=subprocess.run(args,input=SQL.encode('ascii'),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15)
  require(q.returncode==0,'NATURAL_QUEUE_SELECT_EXIT')
  v=parse_queue(q.stdout)
 except BaseException as e:
  return {'at':now(),'trajectory':trajectory,'available':False,'exception_type':type(e).__name__,'fixed_code':'NATURAL_QUEUE_METADATA_UNAVAILABLE'}
 return dict(v,at=now(),trajectory=trajectory,available=True,database_writes=0,private_content_read=False)

def _write_once(path,value):
 data=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb')as f:f.write(data);f.flush();os.fsync(f.fileno())

def send_neutral(driver,trajectory,remaining,*,ordinal,snapshot_sha256):
 h,r,p=_record(driver,trajectory)
 require(type(remaining)is int and 0<remaining<=p['budget_tokens'],'NATURAL_REMAINING_BUDGET')
 require(type(ordinal)is int and 1<=ordinal<=100000,'NATURAL_MESSAGE_ORDINAL')
 require(type(snapshot_sha256)is str and re.fullmatch('[a-f0-9]{64}',snapshot_sha256),'NATURAL_SNAPSHOT_SHA')
 channel=r['task_channel'];require(type(channel)is str and re.fullmatch('[a-z0-9]{26}',channel),'NATURAL_ORIGINAL_TASK_CHANNEL')
 message=p['message']['template_utf8'].format(remaining=remaining)
 root=Path(r['layout'])/'natural-stop-neutral';root.mkdir(mode=0o700,exist_ok=True)
 stem=root/f'message-{ordinal:08d}'
 base={'trajectory':trajectory,'ordinal':ordinal,'remaining_tokens':remaining,'channel_id':channel,'policy_sha256':POLICY_SHA,'template_sha256':TEMPLATE_SHA,'rendered_text_sha256':hashlib.sha256(message.encode()).hexdigest(),'natural_snapshot_sha256':snapshot_sha256}
 # This intent MUST prevent retry even after uncertain HTTP or lost response.
 _write_once(Path(str(stem)+'.intent.json'),dict(base,intent_at=now(),no_auto_retry=True))
 try:
  status,value,_=h.api(r['origins']['mattermost'],'POST','/api/v4/posts',token=r['mm_admin_token'],body={'channel_id':channel,'message':message})
 except BaseException as e:
  v=dict(base,terminal_at=now(),outcome='HTTP_UNKNOWN_NO_RETRY',exception_type=type(e).__name__)
  _write_once(Path(str(stem)+'.terminal.json'),v);return v
 ok=status==201 and type(value)is dict and value.get('channel_id')==channel and type(value.get('id'))is str and re.fullmatch('[a-z0-9]{26}',value['id'])is not None
 v=dict(base,terminal_at=now(),HTTP=status,outcome='SENT'if ok else'HTTP_REJECTED_NO_RETRY',post_id=value['id']if ok else None)
 _write_once(Path(str(stem)+'.terminal.json'),v);return v

# Exact developer-requested fixed callable ports. V1 remains sealed for audit.
ACTIVITY_SQL="""START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;
SELECT state,attempts,COUNT(*) AS event_count,COALESCE(MAX(id),0) AS max_id,COALESCE(SUM(id),0) AS sum_id,COALESCE(MAX(created_at),0) AS max_created_at,COALESCE(MAX(sent_at),0) AS max_sent_at,COALESCE(SUM(sent_at),0) AS sum_sent_at,COALESCE(MAX(next_retry_at),0) AS max_retry_at FROM events GROUP BY state,attempts ORDER BY state,attempts;
ROLLBACK;
"""
ACTIVITY_HEADER='state attempts event_count max_id sum_id max_created_at max_sent_at sum_sent_at max_retry_at'.split()
def parse_activity(raw):
 lines=raw.decode('ascii','strict').splitlines()
 require(bool(lines)and lines[0].split('\t')==ACTIVITY_HEADER,'NATURAL_ACTIVITY_HEADER')
 rows=[];counts={s:0 for s in('pending','sending','retrying','sent','failed')}
 for l in lines[1:]:
  a=l.split('\t');require(len(a)==len(ACTIVITY_HEADER)and a[0]in counts and all(v.isdigit()for v in a[1:]),'NATURAL_ACTIVITY_COLUMNS')
  v={k:(a[i]if i==0 else int(a[i]))for i,k in enumerate(ACTIVITY_HEADER)};counts[v['state']]+=v['event_count'];rows.append(v)
 return counts,rows

def _activity_query(driver,t):
 _,r,_=_record(driver,t);my=[v for v in r['backend_proof']['backend_services']if v['service']=='mysql']
 require(len(my)==1 and re.fullmatch('[a-f0-9]{64}',my[0]['id']),'NATURAL_REGISTERED_MYSQL_ID')
 try:
  z=subprocess.run([*DOCKER,'exec','-i',my[0]['id'],'sh','-c','export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --batch --raw --user=root --connect-timeout=5 --database=omcgitea'],input=ACTIVITY_SQL.encode('ascii'),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15)
 except BaseException:raise RuntimeError('NATURAL_QUEUE_METADATA_UNAVAILABLE')from None
 require(z.returncode==0,'NATURAL_QUEUE_SELECT_EXIT')
 return parse_activity(z.stdout)

class NativeNeutralPorts:
 """Owner-bound exact callable ports; no policy overrides or arbitrary RPC."""
 def __init__(self,driver):self.driver=driver;policy()
 def poll_native_idle(self,trajectory):
  _,r,_=_record(self.driver,trajectory);counts,rows=_activity_query(self.driver,trajectory)
  ledger=self.driver.ledger
  with ledger.mutex:
   # Use the installed, user-approved UNKNOWN-charge-aware frontier, never
   # reopen the ledger or count the already charged forensic UNKNOWN as SENT.
   f=ledger.frontier(trajectory)
   rs=[list(v)for v in ledger.db.execute("SELECT state,COUNT(*),COALESCE(MAX(rowid),0),COALESCE(SUM(input),0),COALESCE(SUM(output),0) FROM requests WHERE trajectory=? GROUP BY state ORDER BY state",(trajectory,))]
   inflight=f['unresolved'];require(type(inflight)is int and inflight>=0,'NATURAL_INFLIGHT_SCHEMA')
  channel=r['task_channel'];require(type(channel)is str and re.fullmatch('[a-z0-9]{26}',channel),'NATURAL_ORIGINAL_TASK_CHANNEL')
  seq=hashlib.sha256(json.dumps({'native_event_metadata':rows,'model_request_metadata':rs},sort_keys=True,separators=(',',':')).encode()).hexdigest()
  return {'trajectory':trajectory,'pending':counts['pending'],'sending':counts['sending'],'retrying':counts['retrying'],'team_model_inflight':inflight,'activity_seq':seq,'channel_identity':channel}
 def post_neutral(self,trajectory,text,intent_id):
  h,r,p=_record(self.driver,trajectory)
  require(type(text)is str and type(intent_id)is str and re.fullmatch('[A-Za-z0-9._:/-]{1,256}',intent_id),'NATURAL_FIXED_POST_IDENTITY')
  prefix,suffix=p['message']['template_utf8'].split('{remaining}')
  require(text.startswith(prefix)and text.endswith(suffix),'NATURAL_FIXED_TEXT')
  middle=text[len(prefix):len(text)-len(suffix)]
  require(bool(middle)and re.fullmatch('[1-9][0-9]{0,7}',middle)and 0<int(middle)<=p['budget_tokens']and text==p['message']['template_utf8'].format(remaining=int(middle)),'NATURAL_FIXED_TEXT')
  channel=r['task_channel'];require(type(channel)is str and re.fullmatch('[a-z0-9]{26}',channel),'NATURAL_ORIGINAL_TASK_CHANNEL')
  root=Path(r['layout'])/'natural-stop-neutral-v2';root.mkdir(mode=0o700,exist_ok=True)
  stem=root/('intent-'+hashlib.sha256(intent_id.encode()).hexdigest())
  base={'trajectory':trajectory,'intent_id':intent_id,'channel_identity':channel,'policy_sha256':POLICY_SHA,'template_sha256':TEMPLATE_SHA,'rendered_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'remaining_tokens':int(middle)}
  _write_once(Path(str(stem)+'.intent.json'),dict(base,intent_at=now(),no_auto_retry=True))
  try:
   status,value,_=h.api(r['origins']['mattermost'],'POST','/api/v4/posts',token=r['mm_admin_token'],body={'channel_id':channel,'message':text})
  except BaseException as e:
   v=dict(base,terminal_at=now(),http_status=None,terminal='UNKNOWN',exception_type=type(e).__name__)
   _write_once(Path(str(stem)+'.terminal.json'),v);return v
  ok=status==201 and type(value)is dict and value.get('channel_id')==channel and type(value.get('id'))is str and re.fullmatch('[a-z0-9]{26}',value['id'])is not None
  v=dict(base,terminal_at=now(),http_status=status,terminal='DELIVERED'if ok else'REJECTED',post_id=value['id']if ok else None)
  _write_once(Path(str(stem)+'.terminal.json'),v);return v
