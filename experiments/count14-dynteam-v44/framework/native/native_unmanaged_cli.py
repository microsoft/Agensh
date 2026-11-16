"""Native tool protocol/security only. No per-tool ledger, callback or custody.

The pending map below is ordinary in-memory JSON-RPC response correlation, not
business accounting or a checkpoint drain gate. Native text prefix integrity is
used ONLY to preserve the unchanged Gitea/Mattermost output scope authorization;
no notice/terminal/dispatch status is used as completion proof. Errors are local
native tool errors and never latch the model ledger/driver FAULT or get retried.
"""
import copy,threading,uuid
from common import need,wire,Refused

def enabled(ledger):return getattr(ledger,'native_unmanaged_cli',False)is True

class NativeTools:
    def __init__(self,ledger):
        need(enabled(ledger),'UNMANAGED_NATIVE_EXPLICIT_OWNER_MODE');self.ledger=ledger
    def __call__(self,identity):return None

def error_reply(message,code):
    return {'jsonrpc':'2.0','id':message.get('id'),'result':{'isError':True,'content':[{'type':'text','text':code}]}}

def broken(session,code):
    # No shared fault or tool-custody records. No respawn, retry or re-dispatch.
    with session.lock:
        session.unmanaged_unavailable=code
        for pending in session.pending.values():
            pending.response=error_reply(pending.request,'NATIVE_TOOL_UNAVAILABLE_NO_RETRY')
            pending.done.set()
        session.pending.clear()

def complete(session,rpc_id,pending):
    if pending.response is None:return
    response=pending.response
    failed='error'in response or bool(isinstance(response.get('result'),dict)and response['result'].get('isError'))
    if not failed:
        guard=session.policy.scope_guard
        integrity=getattr(guard,'requires_native_text_integrity',False)
        if integrity and pending.terminal is None:return
        try:
            authorization=session.policy.authorization_response(response,pending.terminal)if integrity else response
            with session.ledger.tx():session.policy.physical_complete(pending.request,authorization)
        except Refused as failure:
            response=error_reply(pending.request,failure.code)
        except Exception:
            response=error_reply(pending.request,'NATIVE_TOOL_SCOPE_AUTHORIZATION_UNAVAILABLE')
    pending.response=response
    session.pending.pop(rpc_id,None);pending.done.set()

def call(session,message):
    from native_mcp_bridge import Pending,write_all
    # Fixed request scope/capability policy is unchanged. No parent/ticket/tool
    # ownership, operation_start, receipt/event or ledger tool status is used.
    try:kind=session.policy.request(message)
    except Refused as failure:return error_reply(message,failure.code)
    with session.lock:
        if session.closing or getattr(session,'unmanaged_unavailable',None):
            return error_reply(message,'NATIVE_TOOL_UNAVAILABLE_NO_RETRY')
        request=copy.deepcopy(message)
        if kind is not None:
            request['id']=uuid.uuid4().hex;pending=Pending(None,request)
            session.pending[request['id']]=pending
        try:write_all(session.child.stdin,wire(request)+b'\n')
        except Exception:
            broken(session,'NATIVE_TOOL_TRANSPORT_UNAVAILABLE')
            return error_reply(message,'NATIVE_TOOL_UNAVAILABLE_NO_RETRY')
    if kind is None:return None
    pending.done.wait()
    return {**pending.response,'id':message['id']}
