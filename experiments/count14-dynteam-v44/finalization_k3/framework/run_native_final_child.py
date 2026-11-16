#!/usr/bin/env python3
"""Real independent v2.1 child. No fixtures, replay, model/score substitutes."""
from pathlib import Path
import os,re,sys,time,traceback
from common import need,private_dir,regular_fd,hash_file,strict,wire,publish,digest
from native_final_runtime import NativeFinalRuntime
from native_images import NativeImages
from final_host_rpc import HostClient

FIELDS={'schema','manifest','model_policy','input_root','input_policy_sha256','trajectory','k',
        'aux_root','native_directory','profile','services','host_socket','scope','capability',
        'image_freeze','space_home'}


def config_fields(config):
    return set(config)==FIELDS or (set(config)==FIELDS|{'replicate_attempt','point_id'} and type(config['replicate_attempt'])is int and config['replicate_attempt'] in (2,3))

def run(path,expected_sha256):
    path=Path(path);private_dir(path.parent)
    need(path.is_absolute()and path.resolve()==path and hash_file(path)['sha256']==expected_sha256,
         'FINAL_CHILD_EXACT_PRIVATE_CONFIG')
    with regular_fd(path) as fd:
        s=os.fstat(fd);need(s.st_uid==os.geteuid() and s.st_mode&0o777==0o600 and s.st_nlink==1,
                           'FINAL_CHILD_PRIVATE_CONFIG_OWNER_MODE')
    config=strict(path.read_bytes())
    need(type(config)is dict and config_fields(config) and config['schema']=='agensh-native-final-child-v1',
         'FINAL_CHILD_CONFIG_FIELDS')
    ready=path.with_suffix('.ready');deadline=time.monotonic()+30
    while not ready.exists():
        need(time.monotonic()<deadline,'FINAL_CHILD_FIRSTSTART_READY_TIMEOUT_NO_RETRY');time.sleep(.02)
    need(hash_file(path)['sha256']==expected_sha256 and not ready.is_symlink()
         and strict(ready.read_bytes())=={'config_sha256':expected_sha256,'scope':config['scope']},
         'FINAL_CHILD_ORIGINAL_PARENT_RELEASE')
    c=config
    images=NativeImages(c['native_directory'],c['image_freeze'],manifest_sha256=digest(c['manifest']))
    client=HostClient(c['host_socket'],scope=c['scope'],capability=c['capability'])
    runtime=NativeFinalRuntime(manifest=c['manifest'],model_policy=c['model_policy'],input_root=c['input_root'],
        input_policy_sha256=c['input_policy_sha256'],trajectory=c['trajectory'],replicate_index=c['k'],
        aux_root=c['aux_root'],native_directory=c['native_directory'],profile=c['profile'],services=c['services'],
        client=client,images=images,space_home=c['space_home'],**({k:c[k] for k in ('replicate_attempt','point_id')} if 'replicate_attempt' in c else {}))
    runtime.install();report=runtime.run()
    result={'schema':'agensh-native-final-child-terminal-v1','trajectory':c['trajectory'],'k':c['k'],
            'complete':report['complete'],'input_policy_sha256':c['input_policy_sha256'],
            'initial_input_sha256':report['initial_input_sha256'],'frozen_catalog_sha256':report['frozen_catalog_sha256'],
            'finalization_tokens':report['finalization_tokens']}
    if 'replicate_attempt' in c:result.update(replicate_attempt=c['replicate_attempt'],point_id=c['point_id'])
    publish(path.with_suffix('.result.json'),wire(result))
    return result


def main():
    need(len(sys.argv)==3,'FINAL_CHILD_CONFIG_AND_SHA_REQUIRED')
    try:run(sys.argv[1],sys.argv[2])
    except BaseException as e:
        # Narrow authorized failure projection only. Never message, locals,
        # source lines, evaluator payloads, candidate or model output.
        kind=type(e).__name__
        if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,159}',kind)is None:kind='Exception'
        value={'schema':'agensh-native-final-child-sanitized-failure-v1','exception_type':kind,
               'frames':[{'file':f.filename,'line':f.lineno,'function':f.name}
                         for f in traceback.extract_tb(e.__traceback__)]}
        publish(Path(sys.argv[1]).with_suffix('.failure.json'),wire(value));return 1
    return 0

if __name__=='__main__':sys.exit(main())
