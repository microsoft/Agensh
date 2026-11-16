#!/usr/bin/env python3
"""Explicit OWN synthetic fresh child; never a production launcher."""
from pathlib import Path
import json,sys,time
from common import strict,wire,publish
from native_final_runtime import NativeFinalRuntime
from final_host_rpc import HostClient
from native_images import NativeImages
from test_native_fixture_support import install

def main(path):
 path=Path(path);deadline=time.monotonic()+15
 while not path.with_suffix('.ready').exists():
  if time.monotonic()>deadline:raise RuntimeError('OWN_SYNTHETIC_START_FENCE_TIMEOUT')
  time.sleep(.01)
 c=strict(path.read_bytes());state=install(Path(__file__).resolve().parent.parent,mode=c['mode']);mapping=c['freeze']['images']
 def inspect(key):
  r=next(r for r in mapping if key==r['system_manifest_id']or key in r['tags']);return {'Id':r['system_manifest_id'],'RootFS':{'Type':'layers','Layers':r['ordered_diff_ids']}}
 images=NativeImages(c['native_directory'],c['freeze'],manifest_sha256=c['manifest_sha256'],inspect=inspect)
 client=HostClient(c['socket'],scope=c['scope'],capability=c['capability']);runtime=NativeFinalRuntime(manifest=c['manifest'],model_policy=c['model_policy'],input_root=c['input_root'],input_policy_sha256=c['input_policy_sha256'],trajectory=c['trajectory'],replicate_index=c['k'],aux_root=c['aux_root'],native_directory=c['native_directory'],profile=c['profile'],services=c['services'],client=client,images=images,space_home=c['space_home'],space_free=lambda _:10**15)
 try:runtime.install();report=runtime.run()
 finally:publish(path.with_suffix('.counts'),wire(vars(state)))
 publish(path.with_suffix('.result'),wire({'complete':report['complete'],'initial_input_sha256':report['initial_input_sha256'],'frozen_catalog_sha256':report['frozen_catalog_sha256'],'finalization_tokens':report['finalization_tokens']}))
if __name__=='__main__':main(sys.argv[1])
