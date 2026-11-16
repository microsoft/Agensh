"""Standalone minimal GLM health probes; never releases or dispatches search.
One probe/600s, no request retries, own evidence/cost records outside all settings.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_FS_UUID = _count14_os.environ.get('COUNT14_SCRATCH_FS_UUID', '00000000-0000-0000-0000-000000000000')
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
import datetime as dt,fcntl,hashlib,json,os,pathlib,signal,sys,time,urllib.request,urllib.error,uuid
ROOT=pathlib.Path((_C14_SCRATCH + '/cg-count14-seeds-expand8-20261021/batches/batch1'))
HOME=ROOT/'controller/pilot-owner/health'
BASE=_count14_os.environ.get('COUNT14_GLM_LEGACY_BASE_URL', 'https://glm-legacy-gateway.example.invalid/v1')
MODEL='VLLM-GATEWAY-GLM-5.3-FP8'
PERIOD=600;DEADLINE=45;NORMAL_LATENCY=30;OUTPUT=8
BODY=dict(model=MODEL,messages=[dict(role='user',content='Reply OK.')],max_tokens=OUTPUT,temperature=1.,top_p=1.,stream=True,stream_options={'include_usage':True})
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name('.'+p.name+'-'+uuid.uuid4().hex)
 with tmp.open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p);fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
MAX_RESPONSE_BYTES=65536
class ProbeDeadline(TimeoutError):pass
def consume(response, result):
    """Consume complete SSE events. finish_reason does NOT skip later usage.

    DONE permits immediate close; otherwise drain through EOF/deadline so the
    last usage-only chunk after finish_reason is not lost. Only metadata and
    two integer counters survive. No text/tool delta is accumulated or logged.
    """
    total = 0
    data = []
    last_usage = None
    while True:
        raw = response.readline(MAX_RESPONSE_BYTES + 1 - total)
        total += len(raw)
        if total > MAX_RESPONSE_BYTES:
            raise ValueError('SYSTEM_SSE_METADATA_BOUND')
        if not raw:
            break
        line = raw.decode('utf-8', 'strict').rstrip('\r\n')
        if not line:
            if not data:
                continue
            event = '\n'.join(data)
            data.clear()
            if event == '[DONE]':
                result['stream_complete'] = True
                result['stream_terminal_marker'] = 'DONE'
                break
            value = json.loads(event)
            if type(value) is not dict or value.get('error') is not None:
                raise ValueError('SYSTEM_SSE_ERROR_OR_SCHEMA')
            choices = value.get('choices', [])
            if type(choices) is not list:
                raise ValueError('SYSTEM_SSE_CHOICES_SCHEMA')
            for choice in choices:
                if type(choice) is not dict:
                    raise ValueError('SYSTEM_SSE_CHOICE_SCHEMA')
                reason = choice.get('finish_reason')
                if reason is not None:
                    if type(reason) is not str or not reason:
                        raise ValueError('SYSTEM_SSE_FINISH_SCHEMA')
                    result['stream_complete'] = True
                    result['stream_terminal_marker'] = 'finish_reason'
            usage = value.get('usage')
            if usage is not None:
                last_usage = None
                if type(usage) is dict:
                    p = usage.get('prompt_tokens')
                    c = usage.get('completion_tokens')
                    if type(p) is int and type(c) is int and (p >= 0) and (c >= 0) and (p + c > 0):
                        last_usage = (p, c)
        elif line.startswith('data:'):
            value = line[5:]
            data.append(value[1:] if value.startswith(' ') else value)
    if not result['stream_complete']:
        raise ValueError('SYSTEM_SSE_INCOMPLETE')
    if last_usage is None:
        raise ValueError('SYSTEM_SSE_MISSING_FINAL_USAGE')
    p, c = last_usage
    result.update(reported_tokens=p + c, prompt_tokens=p, completion_tokens=c, possible_unmeasured_tokens_upper=0)

def probe(key, identifier, opener=urllib.request.urlopen, clock=time.monotonic):
    started = clock()
    result = dict(request_id=identifier, started_at=now(), http_status=None, error_type=None, reported_tokens=None, possible_unmeasured_tokens_upper=len(json.dumps(BODY).encode()) + 8192 + 256 + OUTPUT, included_in_search_budget=False, prompt_is_fixed_health_only=True, retries=0, stream=True, stream_complete=False, stream_terminal_marker=None)
    request = urllib.request.Request(BASE + '/chat/completions', data=json.dumps(BODY).encode(), method='POST', headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'X-Request-ID': identifier})
    try:
        with opener(request, timeout=DEADLINE) as response:
            result['http_status'] = response.status
            if response.status != 200:
                raise ValueError('SYSTEM_SSE_NON200')
            consume(response, result)
    except urllib.error.HTTPError as error:
        result.update(http_status=error.code, error_type=type(error).__name__)
        if error.code == 503:
            result['possible_unmeasured_tokens_upper'] = 0
    except Exception as error:
        result['error_type'] = type(error).__name__
    result.update(completed_at=now(), elapsed_seconds=clock() - started)
    result['healthy'] = result['http_status'] == 200 and result['stream_complete'] is True and (result['error_type'] is None) and (result['elapsed_seconds'] <= NORMAL_LATENCY)
    return result

def records(home):
 out=[]
 for p in sorted((home/'probes').glob('*/intent.json')):
  intent=json.loads(p.read_text());terminal=p.parent/'terminal.json'
  out.append(dict(intent,**(json.loads(terminal.read_text()) if terminal.exists() else dict(healthy=False,incomplete=True))))
 return out

def streak(values):
 count=0;previous=None
 for r in reversed(values):
  if not r.get('healthy') or (previous is not None and r['sequence']!=previous-1):break
  count+=1;previous=r['sequence']
 return count

def run():
 if os.uname().nodename!=(_C14_HOSTNAME):raise RuntimeError('Wrong probe host')
 import subprocess
 if subprocess.check_output(['findmnt','-T',str(ROOT),'-no','UUID'],text=True).strip()!=(_C14_FS_UUID):raise RuntimeError('Wrong scratch mount')
 HOME.mkdir(parents=True,exist_ok=True)
 with (HOME/'probe.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  save(HOME/'daemon-started.json',dict(pid=os.getpid(),at=now(),source_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
       period_seconds=PERIOD,normal_latency_seconds=NORMAL_LATENCY,max_output_tokens=OUTPUT,search_dispatcher=False))
  while not (HOME/'stop-probes.json').exists():
   rows=records(HOME);last=rows[-1] if rows else None
   due=(dt.datetime.fromisoformat(last['started_at']).timestamp()+PERIOD) if last else 0
   if time.time()<due:time.sleep(min(5,due-time.time()));continue
   sequence=(last['sequence']+1) if last else 1;identifier='count14-health-'+uuid.uuid4().hex;directory=HOME/'probes'/f'{sequence:08d}-{identifier}'
   intent=dict(sequence=sequence,request_id=identifier,started_at=now(),included_in_search_budget=False,max_output_tokens=OUTPUT)
   save(directory/'intent.json',intent)
   def alarm(*args):raise ProbeDeadline('Total probe deadline')
   old=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,DEADLINE)
   try:result=probe((ROOT/'credentials/glm_api_key').read_text().strip(),identifier)
   finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
   result['sequence']=sequence;save(directory/'terminal.json',result)
   rows=records(HOME)
   save(HOME/'health-status.json',dict(at=now(),last_sequence=sequence,last_probe=result,consecutive_successes=streak(rows),
        probe_only=True,never_writes_release_ready=True,total_reported_probe_tokens=sum(r.get('reported_tokens') or 0 for r in rows),
        incomplete_or_unmeasured=sum(r.get('reported_tokens') is None and r.get('possible_unmeasured_tokens_upper',1)>0 for r in rows)))
if __name__=='__main__':run()
