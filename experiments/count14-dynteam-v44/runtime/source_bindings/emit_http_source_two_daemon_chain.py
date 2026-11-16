#!/usr/bin/env python3
"""Actual top-level HTTP source emitter, only generated config-hook bytes vary.

Original HTTP source helper/constructor/commands and deep normal-sealer emitters
are NOT modified. No SOURCE assembly, scientific construction or observation.
"""
from pathlib import Path
from types import FunctionType
import argparse
import hashlib
import importlib.util
import json

HERE=Path(__file__).resolve().parent
HTTP_SHA='eaba1e3e91ab85bf2e472cd65026082e25d59e92157fe124a233188bf7aa3903'
OLD_ALIAS_SHA='3973d537a4989f931230e1a3ab430da73155c37c11d722af448ecd9a40c188d6'
NEW_ALIAS_SHA='6196f94b9d4a27e4c6ae9919f3dc1c5dcc3ea66a63b8359886ec29b67a986cd9'
RUNTIME_FILES=('emit_http_source_two_daemon_chain.py','exact_alias_cold_hook.py',
 'private_config_cold_hook.py','exact_private_config_projection_v1.py','path_bridge.py')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok,code):
 if not ok:raise ValueError(code)


def parent():
 path=HERE.parent/'formal100m-http-source-entry-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/http_source_cold_chain.py'
 need(path.resolve()==path and not path.is_symlink()and sha(path)==HTTP_SHA,'FORMAL_TWO_DAEMON_ORIGINAL_HTTP_SOURCE_HELPER_PIN')
 spec=importlib.util.spec_from_file_location('count14_two_daemon_original_HTTP_source',path)
 value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
 original=parent()
 value=original.private_emitter(tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
 need(value._idle_helper_path==Path(original.__file__),'FORMAL_TWO_DAEMON_KEEP_ACTUAL_HTTP_SOURCE_HELPER')
 before=value.emit.__code__;constants=before.co_consts
 candidates=[(i,v)for i,v in enumerate(constants)if type(v)is str and
  v.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
 need(len(candidates)==1,'FORMAL_TWO_DAEMON_ONE_EXISTING_GENERATED_SOURCE_CONSTANT')
 i,text=candidates[0]
 old_path=str(HERE.parent/'formal100m-private-config-cold-wip-v2-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/exact_alias_cold_hook.py')
 new_path=str(HERE/'exact_alias_cold_hook.py')
 need(text.count(old_path)==text.count(OLD_ALIAS_SHA)==1 and sha(new_path)==NEW_ALIAS_SHA,
  'FORMAL_TWO_DAEMON_EXACT_OLD_HOOK_PATH_AND_SHA_ANCHORS')
 updated=text.replace(old_path,new_path,1).replace(OLD_ALIAS_SHA,NEW_ALIAS_SHA,1)
 need(updated.replace(new_path,old_path,1).replace(NEW_ALIAS_SHA,OLD_ALIAS_SHA,1)==text,
  'FORMAL_TWO_DAEMON_GENERATED_HOOK_PATH_HASH_EXACT_INVERSE')
 changed=list(constants);changed[i]=updated;code=before.replace(co_consts=tuple(changed))
 need(code.co_code==before.co_code and code.replace(co_consts=constants)==before,
  'FORMAL_TWO_DAEMON_ORIGINAL_EMIT_BYTECODE_ONE_CONST_INVERSE')
 fn=FunctionType(code,value.emit.__globals__,value.emit.__name__,value.emit.__defaults__,value.emit.__closure__)
 fn.__kwdefaults__=value.emit.__kwdefaults__;value.emit=fn
 value._idle_pin_paths=tuple(dict.fromkeys((*value._idle_pin_paths,*(HERE/n for n in RUNTIME_FILES))))
 proof=dict(original_HTTP_source_sha256=HTTP_SHA,original_HTTP_source_helper_path=str(original.__file__),
  previous_alias_hook_path=old_path,previous_alias_hook_sha256=OLD_ALIAS_SHA,
  actual_alias_hook_path=new_path,actual_alias_hook_sha256=NEW_ALIAS_SHA,
  one_generated_source_constant_changed=True,generated_hook_path_hash_inverse=True,emit_co_code_unchanged=True,
  original_HTTP_helper_constructor_commands_and_parent_chain_unchanged=True)
 if hasattr(value,'_formal_exact_alias_proof'):
  value._formal_exact_alias_proof=dict(value._formal_exact_alias_proof,hook_path=new_path,hook_sha256=NEW_ALIAS_SHA)
 value._two_daemon_HTTP_source_proof=proof;return value


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,
         tester_bindings_sha256=None,new_bindings=None):
 original=parent();fn=FunctionType(original.emit.__code__,dict(original.emit.__globals__,private_emitter=private_emitter),
  original.emit.__name__,original.emit.__defaults__,original.emit.__closure__)
 fn.__kwdefaults__=original.emit.__kwdefaults__
 result=fn(bindings_path,bindings_sha256,destination=destination,tester_bindings_path=tester_bindings_path,
  tester_bindings_sha256=tester_bindings_sha256,new_bindings=new_bindings)
 old=result['formal_exact_alias_cold_suffix']
 need(old['frozen_hook_sha256']==OLD_ALIAS_SHA,'FORMAL_TWO_DAEMON_TRUTHFUL_INHERITED_HOOK_PROOF_REQUIRED')
 # This is a new result object, not a rewrite of any old receipt or record.
 result['formal_exact_alias_cold_suffix']=dict(old,previous_frozen_hook_sha256=OLD_ALIAS_SHA,
  frozen_hook_sha256=NEW_ALIAS_SHA,actual_frozen_hook_path=str(HERE/'exact_alias_cold_hook.py'),
  generated_hook_path_hash_rebound_only=True)
 result['formal_two_daemon_HTTP_source_cold_suffix']=dict(original_HTTP_source_sha256=HTTP_SHA,
  original_HTTP_source_helper_preserved=True,actual_alias_hook_sha256=NEW_ALIAS_SHA,
  actual_config_hook_sha256='bc226f9791ebda3ce6d074f73aaeab9076175ab80dab4c11435cbd0b70108461',
  actual_declared_config_helper_sha256='c170564e5407913e06e37136c1b04e38de475146ff9e115aab24a123dda51bff',
  original_commands_constructor_and_co_code_unchanged=True,source_or_owner_constructed=False,
  actual_daemon_observation=False,models=0)
 return result


def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--bindings',required=True);p.add_argument('--bindings-sha256',required=True)
 p.add_argument('--destination',required=True);p.add_argument('--tester-bindings')
 p.add_argument('--tester-bindings-sha256');p.add_argument('--new-bindings');a=p.parse_args(argv)
 try:
  print(json.dumps(emit(a.bindings,a.bindings_sha256,destination=a.destination,
   tester_bindings_path=a.tester_bindings,tester_bindings_sha256=a.tester_bindings_sha256,new_bindings=a.new_bindings),sort_keys=True));return 0
 except Exception as error:
  locations=[];tb=error.__traceback__
  while tb:locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
  print(json.dumps(dict(PUBLIC_code='FORMAL_TWO_DAEMON_HTTP_EMIT_REFUSED_RETAIN_NO_RETRY',
   exception_type=type(error).__name__,locations=locations,messages_or_locals_exported=False),sort_keys=True));return 2


if __name__=='__main__':raise SystemExit(main())
