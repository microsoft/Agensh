"""Install the byte-identical pinned original CLI. No tool instrumentation."""
from pathlib import Path
import hashlib,os
from common import need,hash_file,publish,wire,regular_fd,sync_dir
APP_SHA='cb5087c60e67ad545c83ba0d91b9a3edcdec5be16c7d981d4ecbe6c21dfb4dba'
BASE=Path(__file__).resolve().parent
CLIENT='native-cli-tool-receipt-v1/native_cli_tool_receipt.mjs'
CLI_DIST='/opt/copilot-cli/node_modules/@github/copilot-linux-x64'
CLI_WRAPPER_PATH='/usr/local/bin/copilot-wrapped'
CLI_WRAPPER='#!/bin/sh\nset -eu\nexport COPILOT_CLI_DIST_DIR=/opt/copilot-cli/node_modules/@github/copilot-linux-x64\nexport COPILOT_AUTO_UPDATE=false\nfor argument do\n  case "$argument" in\n    --prefer-version|--prefer-version=*) printf \'%s\\n\' COUNT14_CLI_VERSION_SELECTOR_FORBIDDEN >&2; exit 64;;\n  esac\ndone\nexec /opt/copilot-cli/node_modules/@github/copilot-linux-x64/copilot "$@"\n'
def build_app(raw):
    need(type(raw)is bytes and hashlib.sha256(raw).hexdigest()==APP_SHA,'CLI_OVERLAY_ORIGINAL_APP_PIN')
    return raw

def install(original_app,destination):
    source=Path(original_app);pin=hash_file(source);raw=build_app(source.read_bytes())
    d=Path(destination);need(d.is_absolute()and d.resolve()==d and not d.exists(),'CLI_OVERLAY_NEW_ROOT');d.mkdir(mode=0o700)
    need(hash_file(source)==pin,'CLI_OVERLAY_ORIGINAL_CHANGED_DURING_READ')
    publish(d/'app.js',raw,mode=0o400)
    # Dormant mount-layout compatibility leaf. Original app never imports it;
    # no callbacks, tickets, receipt service or CLI tool state machine exists.
    publish(d/'native_cli_tool_receipt.mjs',(BASE/CLIENT).read_bytes(),mode=0o400)
    publish(d/'copilot-wrapped',CLI_WRAPPER.encode(),mode=0o500)
    with regular_fd(d/'copilot-wrapped')as fd:os.fchmod(fd,0o555);os.fsync(fd)
    sync_dir(d)
    receipt={'schema':'agensh-original-cli-unmanaged-install-v1','original_app':pin,'installed_app':hash_file(d/'app.js'),'client':hash_file(d/'native_cli_tool_receipt.mjs'),'native_exec_wrapper':hash_file(d/'copilot-wrapped'),'native_tool_instrumentation':False,'callback_service_required':False,'original_app_byte_identical':True,'launcher':{'worker_path':CLI_WRAPPER_PATH,'mode':'0555','read_only':True,'exec':CLI_DIST+'/copilot','same_registered_pid':True,'environment':{'COPILOT_CLI_DIST_DIR':CLI_DIST,'COPILOT_AUTO_UPDATE':'false'},'npm_spawn_parent':False,'original_arguments_preserved':True}}
    publish(d/'ORIGIN.json',wire(receipt),mode=0o400);return receipt

# Legacy test-fixture reference constants only; never used by native installer.
IMPORT='''import {withOriginalNativeTool as __count14OriginalTool,originalNativeToolNotExecuted as __count14NoExecution,nativeMcpRequestMeta as __count14OriginalMcpMeta,nativeShellCreate as __count14ShellCreate,nativeShellStart as __count14ShellStart,nativeShellDispose as __count14ShellDispose} from "/opt/count14/native_cli_tool_receipt.mjs";
'''
CALLBACK='},S=await g(f,b);s=Date.now()-m,'
WRAPPED='},S=await __count14OriginalTool(a,l,f,()=>g(f,b));s=Date.now()-m,'
NO_EXEC='if(l.failureResultJson)d=JSON.parse(l.failureResultJson);else{'
WRAPPED_NO_EXEC='if(l.failureResultJson){d=JSON.parse(l.failureResultJson);await __count14NoExecution(a,l);}else{'
METHOD='async callTool(e,n,r,o){let s=0,{originalCall:a,plan:l}=e;'
END='async getModel(){let e=this.clientOptions.model,'
def original_method(raw):
    need(type(raw)is bytes and hashlib.sha256(raw).hexdigest()==APP_SHA,'CLI_OVERLAY_ORIGINAL_APP_PIN')
    text=raw.decode();start=text.index(METHOD);end=text.index(END,start)
    return text[start:end]
