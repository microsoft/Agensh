"""One fixed local metadata timeout 15 ->300; full guards/no replay unchanged."""
from pathlib import Path
import ast,copy,hashlib,inspect,textwrap
from common import need,hash_file
import final_host_rpc as rpc
FILE_SHA='8a1a5a2fe975d2a38988dc3edbd10213f68b45bc91b72727a6284a082c8782a8'
TIMEOUT_SECONDS=300

def build(original,record_type=lambda _:None):
 need(hash_file(Path(inspect.getsourcefile(original)))['sha256']==FILE_SHA and original.__qualname__=='HostClient.call','AUX_RPC_WAIT_EXACT_PUBLIC_SOURCE')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));old=copy.deepcopy(tree);fn=tree.body[0]
 matches=[n for n in ast.walk(fn)if isinstance(n,ast.Call)and ast.unparse(n.func)=='client.settimeout']
 need(len(matches)==1 and len(matches[0].args)==1 and isinstance(matches[0].args[0],ast.Constant)and matches[0].args[0].value==15,'AUX_RPC_WAIT_ONLY_FIXED_15S')
 matches[0].args[0]=ast.Constant(TIMEOUT_SECONDS)
 handlers=[n for n in ast.walk(fn)if isinstance(n,ast.ExceptHandler)and n.type is not None and ast.unparse(n.type)=='Exception'and n.name=='e']
 need(len(handlers)==1,'AUX_RPC_WAIT_EXACT_IO_EXCEPTION_HANDLER')
 handlers[0].body.insert(0,ast.parse('_record_rpc_error_type(type(e).__name__)').body[0])
 # This reverse transform is also checked in tests: no other call/assert/branch
 # may change, and no retry is introduced for a possible SENT request.
 ns=dict(original.__globals__);ns['_record_rpc_error_type']=record_type
 exec(compile(ast.fix_missing_locations(tree),'<aux-metadata-rpc-wait-original-call>','exec'),ns)
 return ns['call'],tree,old

def install(record_type=lambda _:None):
 need(not getattr(rpc.HostClient.call,'_metadata_wait_repair',False),'AUX_RPC_WAIT_INSTALL_ONCE')
 fixed,_,_=build(rpc.HostClient.call,record_type);fixed._metadata_wait_repair=True
 rpc.HostClient.call=fixed
 return {'schema':'aux-local-metadata-rpc-wait-v1','old_local_socket_timeout_seconds':15,'local_socket_timeout_seconds':TIMEOUT_SECONDS,'server_frame_bound_timeout_unchanged':True,'identity_nonce_capacity_budget_guards_unchanged':True,'model_evaluator_or_provider_timeouts_unchanged':True,'transport_retries':0}
