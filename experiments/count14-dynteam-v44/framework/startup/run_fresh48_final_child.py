#!/usr/bin/env python3
"""Fresh native v2.1 child: only metadata RPC/AUX deadline/session header seams.

No old historical attempt allowances, no old root wrapper chains. Source input,
model body, original v2.1 turns/test logic and usage validation stay unchanged.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
import sys

def install(config_path):
 from common import need,hash_file
 from metadata_rpc_wait import install as rpc
 from aggregate_final_binding import install as branch_rng
 from glm_session_header import aux_transport
 from aux_timeout import install_port
 import native_model_port
 from expansion100_contract import NEW_ROOT,NEW_EID
 branch_rng();rpc()
 original=native_model_port.NativeModelPort.wrap_stream
 need(not getattr(original,'_fresh48_aux_seams',False),'FRESH48_CHILD_SEAMS_ONCE')
 def wrap(port,stream):
  m=port.binding.profile.manifest
  need(m['root']==NEW_ROOT and m['experiment_id']in(NEW_EID,NEW_EID+'-fork16plus4'),
   'FRESH48_CHILD_EXACT_MAIN_OR_BRANCH_SCOPE')
  header=aux_transport(stream,port,key_path=Path(NEW_ROOT)/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key'),
   receipt=Path(config_path).with_suffix('.glm-session.json'))
  return install_port(port,original,header,Path(config_path).with_suffix('.aux-timeout.json'))
 wrap._fresh48_aux_seams=True;native_model_port.NativeModelPort.wrap_stream=wrap
 return {'models':0,'AUX_timeout_minimum':900,'local_metadata_rpc_timeout':300,
  'search_timeout_changed':False,'replicate_attempt_session':True,'historical_allowances_installed':False}

def main():
 from common import need
 need(len(sys.argv)==3,'FRESH48_CHILD_ORIGINAL_CONFIG_AND_HASH_ARGUMENTS')
 install(sys.argv[1])
 from run_native_final_child import main as original
 return original()
if __name__=='__main__':raise SystemExit(main())
