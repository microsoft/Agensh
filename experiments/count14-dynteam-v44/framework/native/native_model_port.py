"""Actual original v54 request-policy seam to shared host model custody.

No new model client/classifier is introduced. The original stream_call performs
its actual SSE/usage/finish/DONE/integrity checks; only after it returns is the
shared physical permit closed. Original failure/timeout/retry/charging bodies
run unchanged. Missing host control is a BaseException domain failure so native
fallback cannot silently turn missing infrastructure into a qualified result.
"""
from contextlib import contextmanager
from pathlib import Path
import ast,copy,hashlib,json,threading,time,uuid
from common import digest,sha,hash_file,Refused
from final_host_rpc import ControlFailure

def need(condition,code):
    if not condition:raise ControlFailure(code)

def restore_reasoning_alias(response,raw_path):
    """Preserve the original FINAL assistant context across the PR1 rename.

    Called only AFTER original stream_call validated usage/finish/DONE/tool
    integrity. Raw SSE remains byte-exact. Original legacy chunks win when
    both aliases are present; mixed old/new chunks retain their stream order.
    No content/tool/usage/finish, request, ledger or original receipt is edited.
    """
    choices=response.get('choices') if type(response)is dict else getattr(response,'choices',None)
    if not choices or len(choices)!=1:return response
    choice=choices[0]
    message=choice.get('message') if type(choice)is dict else getattr(choice,'message',None)
    if message is None:return response
    from stream_integrity_v514 import events
    parts=[];new_alias=False
    for event in events(Path(raw_path).read_bytes()):
        for choice in event.get('choices')or[]:
            delta=choice.get('delta')or{}
            legacy=delta.get('reasoning_content')
            renamed=delta.get('reasoning')
            if legacy is not None:
                if type(legacy)is str:parts.append(legacy)
            elif type(renamed)is str:
                parts.append(renamed);new_alias=True
    if new_alias:
        value=''.join(parts)
        if type(message)is dict:message['reasoning_content']=value
        else:message.reasoning_content=value
    return response

class NativeModelPort:
    def __init__(self,client,*,binding,native_directory):
        self.client=client;self.binding=binding;self.code=Path(native_directory);self.local=threading.local();self.lock=threading.RLock()
        self.transport_sha=hash_file(self.code/'cc_streaming.py')['sha256'];self.classifier_sha=hash_file(self.code/'request_policy.py')['sha256'];self.guard_source=(self.code/'maintenance_guard_v54.py').read_text()
        self.guard=type('NativeIndependentMaintenance',(),{})()
        namespace={'time':time,'paused':self.paused,'state':self.state,'request_pause':self.request_pause}
        tree=ast.parse(self.guard_source);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ('timeout','failure','wait_finalizer')];need(len(nodes)==3,'NATIVE_GUARD_FUNCTIONS_REQUIRED')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(self.code/'maintenance_guard_v54.py'),'exec'),namespace)
        self.original_guard=namespace;self.MaintenancePause=type('MaintenancePause',(Exception,),{})
    def state(self):return self.client.call('state')
    def paused(self):return self.state()['mode']=='PAUSED'
    def before_request(self):
        self.authorize()
        if self.paused():raise self.MaintenancePause()
    def authorize(self):
        try:self.binding.authorize()
        except Refused as e:raise ControlFailure(e.code)from None
    def request_pause(self,reason,**metadata):
        # Original guard hands only framework-generated public metadata to this
        # fixed method; no exception messages, model or evaluator payloads.
        return self.client.call('pause',metadata)
    def wait_finalizer(self,ledger,on_status):return self.original_guard['wait_finalizer'](ledger,on_status)
    @contextmanager
    def api_slot(self,kind,purpose='search'):
        self.authorize();need(kind=='api-'+self.binding.row['setting']and purpose=='finalization','NATIVE_FINAL_MODEL_SLOT_SCOPE')
        permit='aux-'+uuid.uuid4().hex
        while self.client.call('acquire',{'permit_id':permit})is None:
            self.authorize();time.sleep(.2) # Local unsent HOLD, not model retry.
        value={'permit_id':permit,'sent':False,'physical_terminal':False,'request_id':None};self.local.active=value
        try:
            yield
            need(not value['sent']or value['physical_terminal'],'NATIVE_MODEL_RETURN_WITHOUT_TERMINAL')
        except BaseException:
            if value['sent']and not value['physical_terminal']:self.client.call('unknown',{'permit_id':permit,'proof_sha256':digest({'kind':'NATIVE_STREAM_OR_CONTROL_EXCEPTION','request_id':value['request_id']})})
            raise
        finally:
            if not value['sent']:self.client.call('cancel_unsent',{'permit_id':permit})
            self.local.last=value;del self.local.active
    def begin_request(self,ledger,identifier,role):
        self.before_request();need(role=='single','NATIVE_FINAL_LEDGER_ROLE_ABI');value=getattr(self.local,'active',None);need(value is not None and not value['sent'],'NATIVE_SHARED_MODEL_SLOT_REQUIRED')
        # SENT is conservative and durable before network. Any failure afterwards
        # retains custody, including before native begin can publish its receipt.
        while True:
            result=self.client.call('sent',{'permit_id':value['permit_id'],'request_id':identifier})
            need(type(result)is dict and set(result)=={'recorded','state'}and type(result['recorded'])is bool,'NATIVE_SENT_CONTROL_ABI')
            if result=={'recorded':True,'state':'SENT'}:break
            need(result=={'recorded':False,'state':'HELD_UNSENT_PAUSED'},'NATIVE_SENT_CONTROL_NOT_UNSENT_HOLD')
            # Keep this native reservation/permit/request ID and call stack.
            # No model dispatch/reclassification, new ID, replay or auto-resume.
            self.authorize();time.sleep(.2)
        value.update(sent=True,request_id=identifier)
        ledger.begin(identifier,role)
    def wrap_stream(self,original):
        def stream(original_completion,options,**kwargs):
            self.authorize();value=getattr(self.local,'active',None);need(value is not None and value['sent']and not value['physical_terminal'],'NATIVE_SHARED_MODEL_SENT_REQUIRED')
            need(options.get('extra_headers',{}).get('X-Request-ID')==value['request_id'],'NATIVE_MODEL_REQUEST_ID_CHANGED')
            raw=original(original_completion,options,**kwargs)
            # Exact original implementation already validates usage + finish +
            # [DONE] + received tool-call integrity before returning.
            raw_path=kwargs.get('raw_path');need(raw_path is not None,'NATIVE_ORIGINAL_RAW_STREAM_REQUIRED')
            restore_reasoning_alias(raw,raw_path)
            receipt=digest({'request_id':value['request_id'],'raw_provider_stream':hash_file(raw_path)})
            self.client.call('terminal',{'permit_id':value['permit_id'],'proof':{'kind':'ORIGINAL_STREAM_RETURNED_VALID_USAGE_AND_FINISH','provider_terminal':True,'request_id':value['request_id'],'transport_source_sha256':self.transport_sha,'receipt_sha256':receipt}});value['physical_terminal']=True
            return raw
        return stream
    def failure(self,error,transport,**metadata):
        value=getattr(self.local,'last',None);need(value is not None and value['request_id']==metadata.get('request_id'),'NATIVE_FAILURE_WITHOUT_ORIGINAL_REQUEST')
        classification=metadata.get('classification')
        if classification in ('REJECTED_PREGEN','RETRYABLE_REJECTED')and not value['physical_terminal']:
            need(not transport.get('stream_started',False),'NATIVE_PREGEN_WITH_STARTED_STREAM')
            self.client.call('pregen',{'permit_id':value['permit_id'],'proof':{'kind':'ORIGINAL_V54_PREGEN_CLASSIFICATION','classification':classification,'stream_started':False,'classifier_source_sha256':self.classifier_sha,'receipt_sha256':digest({'request_id':value['request_id'],'classification':classification,'http_status':transport.get('http_status')}),'request_id':value['request_id']}});value['physical_terminal']=True
        return self.original_guard['failure'](error,transport,**metadata)
