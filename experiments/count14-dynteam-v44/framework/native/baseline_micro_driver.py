#!/usr/bin/env python3
"""OPS one-shot driver: <=6 tiny requests, no retries, metadata-only receipts.

Requires an independently launched relay capped at six sends with fresh ledger.
No credentials/request/response text are printed or written to receipts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import urllib.parse
from protocol import Rejected,need,wire,mapped_usage
from feasibility_relay import private_file,strict_json,NoRedirect

TOOL=dict(type='function',name='own_echo',description='Toy echo for Agensh feasibility only.',strict=True,
          parameters=dict(type='object',properties=dict(value=dict(type='string')),required=['value'],additionalProperties=False))

def schema(response):
    need(type(response)is dict and response.get('object')=='response','RESPONSE_SHAPE')
    need(response.get('status')=='completed','RESPONSE_NOT_COMPLETE')
    need(type(response.get('output'))is list,'OUTPUT_SHAPE')
    u=response.get('usage');need(type(u)is dict and all(type(u.get(k))is int and u[k]>=0 for k in ('input_tokens','output_tokens','total_tokens'))and u['total_tokens']==u['input_tokens']+u['output_tokens'],'USAGE_SHAPE')
    return dict(status=response['status'],output_types=[r['type']for r in response['output']],usage=u,response_sha256=hashlib.sha256(wire(response)).hexdigest())

class Client:
    def __init__(self,base,key):
        u=urllib.parse.urlsplit(base)
        need(u.scheme=='http'and u.hostname in ('127.0.0.1','localhost','::1')and not u.username and not u.password and not u.query and not u.fragment and u.path in ('','/'),'LOCAL_RELAY_BASE_REQUIRED')
        self.base,self.key=base.rstrip('/'),key;self.attempts=0
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def usage(self):
        r=urllib.request.Request(self.base+'/admin/usage',headers={'Authorization':'Bearer '+self.key})
        with self.opener.open(r,timeout=10)as out:return strict_json(out.read(65537))
    def send(self,body):
        need(self.attempts<6,'DRIVER_SIX_REQUEST_BOUND');self.attempts+=1
        req=urllib.request.Request(self.base+'/v1/responses',data=wire(body),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        with self.opener.open(req,timeout=180)as out:
            if not body.get('stream'):return strict_json(out.read(1048577)),None
            need(out.headers.get_content_type()=='text/event-stream','SSE_CONTENT_TYPE');events=[];event_type=None;parts=[];total=0
            for raw in out:
                total+=len(raw);need(total<=1048576,'MICRO_SSE_BOUND');line=raw.decode().rstrip('\r\n')
                if line.startswith('event:'):event_type=line[6:].strip()
                elif line.startswith('data:'):parts.append(line[5:].lstrip(' '))
                elif not line and parts:
                    item=strict_json('\n'.join(parts));parts=[];need(item.get('type')==event_type,'SSE_EVENT_TYPE_MISMATCH');events.append(item)
            need(bool(events)and events[0]['type']=='response.created','SSE_CREATED')
            need([e['sequence_number']for e in events]==list(range(len(events))),'SSE_SEQUENCE')
            need(events[-1]['type']=='response.completed','SSE_TERMINAL')
            return events[-1]['response'],dict(event_types=[e['type']for e in events],events=len(events),sequence_contiguous=True)

def run(client,model,save):
    pre=client.usage();need(all(r['requests']==0 for r in pre),'MICRO_REQUIRES_FRESH_IDENTITY_LEDGER')
    rows=[]
    def execute(label,**changes):
        req=dict(model=model,input='Return only ACK.',max_output_tokens=256,store=True);req.update(changes)
        response,events=client.send(req);receipt=dict(step=label,attempt=client.attempts,**schema(response),stream=events)
        rows.append(receipt);save(label,receipt);return response
    execute('01_nonstream_text')
    first=execute('02_nonstream_function',input='Call own_echo with value OWN.',tools=[TOOL],tool_choice=dict(type='function',name='own_echo'))
    calls=[x for x in first['output']if x['type']=='function_call'];need(len(calls)==1 and calls[0]['name']=='own_echo','EXACT_ONE_FUNCTION_REQUIRED')
    # Only invented toy argument structure, never printed or saved.
    need(strict_json(calls[0]['arguments'])==dict(value='OWN'),'TOY_ARGUMENTS')
    execute('03_nonstream_tool_continuation',input=[dict(type='function_call_output',call_id=calls[0]['call_id'],output='OWN_OK')],previous_response_id=first['id'],tools=[TOOL],tool_choice='none')
    execute('04_stream_text',stream=True)
    streamed=execute('05_stream_function',stream=True,input='Call own_echo with value OWN.',tools=[TOOL],tool_choice=dict(type='function',name='own_echo'))
    calls=[x for x in streamed['output']if x['type']=='function_call'];need(len(calls)==1 and calls[0]['name']=='own_echo','EXACT_ONE_STREAM_FUNCTION_REQUIRED')
    need(strict_json(calls[0]['arguments'])==dict(value='OWN'),'TOY_STREAM_ARGUMENTS')
    execute('06_stream_tool_continuation',stream=True,input=[dict(type='function_call_output',call_id=calls[0]['call_id'],output='OWN_OK')],previous_response_id=streamed['id'],tools=[TOOL],tool_choice='none')
    post=client.usage();need(len(post)==1 and post[0]['requests']==6 and post[0]['accounted_requests']==6 and post[0]['unknown_or_inflight']==0,'LEDGER_NOT_CLOSED')
    need(post[0]['input_tokens']==sum(r['usage']['input_tokens']for r in rows)and post[0]['output_tokens']==sum(r['usage']['output_tokens']for r in rows),'TOKEN_TOTAL_MISMATCH')
    return dict(passed=True,attempts=client.attempts,rows=rows,usage=post,category='agensh_feasibility',gate2_to_4=None)

def main():
    p=argparse.ArgumentParser();p.add_argument('--relay',required=True);p.add_argument('--local-key-file',required=True);p.add_argument('--model',required=True);p.add_argument('--out',required=True);p.add_argument('--execute-six-once',action='store_true');a=p.parse_args()
    need(a.execute_six_once,'EXPLICIT_EXECUTE_REQUIRED');os.umask(0o077);out=Path(a.out);out.mkdir(mode=0o700)
    (out/'started.json').write_bytes(wire(dict(at_ns=time.time_ns(),pid=os.getpid(),max_requests=6,category='agensh_feasibility'))+b'\n')
    key=private_file(a.local_key_file).decode().strip();client=Client(a.relay,key)
    def save(label,row):
        with (out/(label+'.json')).open('xb')as f:f.write(wire(row)+b'\n')
    try:result=run(client,a.model,save)
    except Exception as e:
        result=dict(passed=False,attempts=client.attempts,exception_type=type(e).__name__,code=e.code if isinstance(e,Rejected)else('HTTP_'+str(e.code)if isinstance(e,urllib.error.HTTPError)else'DIAGNOSTIC_FAILURE_NO_RETRY'),category='agensh_feasibility',automatic_retry=False)
    with (out/'result.json').open('xb')as f:f.write(wire(result)+b'\n')
    print(json.dumps({k:result[k]for k in ('passed','attempts','category')},sort_keys=True))
    raise SystemExit(0 if result['passed']else 1)

if __name__=='__main__':main()
