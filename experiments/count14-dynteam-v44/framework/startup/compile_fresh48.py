#!/usr/bin/env python3
"""Private metadata-only compile in the prepared exact-mode interpreter."""
from pathlib import Path
import sys
from common import need,hash_file,strict,wire,publish
from fresh48_scope import selected
from run_native_scientific6 import read_configuration,compile_configuration
from expansion100_contract import write_authorization,NEW_ROOT

def main(mode):
 root,_=selected(mode);root=Path(root);need(str(root)==NEW_ROOT,'FRESH48_CORRECT_FIXED_CONTRACT_IMPORT_FIRST')
 source=root/'config/private-derived-x48.json';c=read_configuration(source,hash_file(source)['sha256'])
 from fresh48_reader import stage
 stage(strict((root/'config/PUBLIC_READER_SOURCE.json').read_bytes()),root/'config/reader120/budget_pause_clock.js')
 result=compile_configuration(c)
 publish(root/'config/private-launch-x48-v4.json',wire(result))
 authorization=write_authorization(result['manifest'])
 from fresh48_bootstrap import launch_metadata
 publish(root/'config/FIXED_LAUNCH_V4.json',wire(launch_metadata(mode=mode,
  compiled_sha=hash_file(root/'config/private-launch-x48-v4.json')['sha256'])))
 publish(root/'config/PUBLIC_COMPILED_SCOPE.json',wire({'schema':'agensh-v2-fresh48-compiled-scope-v1',
  'root':str(root),'mode':mode,'configuration_sha256':hash_file(root/'config/private-launch-x48-v4.json')['sha256'],
  'authorization':authorization,'same_approved_task_sha256':result['manifest']['protocol']['task_description'],
  'source_and_model_changed':False,'models':0,'workers_started':0}))
 return 0
if __name__=='__main__':raise SystemExit(main(sys.argv[1]))
