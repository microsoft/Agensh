#!/usr/bin/env python3
"""One actual formal helper/emitter adds explicit kernel-control publication.

Original service/financial/HTTP/T binders and commands are retained. Nothing
retires, issues, captures or publishes during import/factory verification.
Only the exact no-argument opcode reaches the original typed source guard.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib
import importlib.util
import json

PARENT_SHA256='27fd9b4eb32c432c56924ea9bf2ae4dfcec31af3bca09e8a403bcf02812a5cdd'
SOURCE_SHA256='8fb3300c24ade2a62d3e59d134eb4d988b80166ee993be2b9ecd4c25dab9a54e'
OP='PUBLISH_NORMAL_INERT_KERNEL_CONTROLS'
RETAINED_PARENT_NAMESPACE=None
RETAINED_PRIVATE_FACTORY=None
RETAINED_ORIGINAL_OWNER=None
RETAINED_ORIGINAL_LEDGER=None


def parent():
 path=Path(__file__).resolve().parents[1]/'formal100m-native-control-source-entry-cold-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/native_source_cold_chain.py'
 if path.resolve()!=path or path.is_symlink()or hashlib.sha256(path.read_bytes()).hexdigest()!=PARENT_SHA256:
  raise ValueError('KERNEL_SOURCE_ENTRY_FIXED_ORIGINAL_SERVICES_CHAIN_PIN')
 spec=importlib.util.spec_from_file_location('count14_kernel_source_native_parent',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def source_api():
 module=importlib.import_module('kernel_control_source_supplement');p=Path(module.__file__)
 expected=Path(__file__).resolve().parents[1]/'formal100m-kernel-control-source-supplement-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/kernel_control_source_supplement.py'
 if p!=expected or p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=SOURCE_SHA256:
  raise ValueError('KERNEL_SOURCE_ENTRY_FIXED_REAL_SOURCE_PUBLICATION_COMPONENT')
 host=p.with_name('kernel_control_host_restore.py')
 if host.resolve()!=host or host.is_symlink()or hashlib.sha256(host.read_bytes()).hexdigest()!='26d2f20d641e177e42080ee37ab71bcc8dfa4d9efdf5eb15d8575db003e487d4':
  raise ValueError('KERNEL_SOURCE_ENTRY_FIXED_KERNEL_HOST_CONTROL_COMPONENT')
 module.verify_sources();return module


def verify_sources():
 original=parent();original.verify_sources();source=source_api()
 return dict(parent_sha256=PARENT_SHA256,kernel_source_sha256=SOURCE_SHA256,
  kernel_source_module=str(Path(source.__file__)),new_opcode=OP,original_binders_and_commands_unchanged=True)


def publish_kernel(owner):
 from bounded_metadata_ro import ReadBudget
 # S itself verifies the original same-live-source T, services publication,
 # three locks and equations. No caller-supplied path, cap or bypass flag.
 source=source_api();reference=source.publish_registered(owner,read_budget=ReadBudget())
 return dict(schema='count14-kernel-source-actual-cold-entry-publication-v1',
  kernel_control_source_reference=reference,original_T_and_service_financial_sidecars_unmodified=True,
  source_metadata_only=True,inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,
  whole_runnable_ready=False,new_dispatcher=False)


def load_private_factory(*,tester_sources=None,tester_companion=None,approved_repair_sources=()):
 verify_sources()
 return parent().load_private_factory(tester_sources=tester_sources,tester_companion=tester_companion,
  approved_repair_sources=approved_repair_sources)


def verify_actual_formal_import_graph():
 proof=parent().verify_actual_formal_import_graph();pins=verify_sources()
 return dict(schema='count14-kernel-native-services-source-actual-import-graph-v1',parent=proof,source_pins=pins,
  kernel_publication_explicit_only=True,original_owner_constructed=False,
  safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest,
 tester_bindings_path=None,tester_bindings_sha256=None,approved_repair_sources=()):
 global RETAINED_PARENT_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
 if RETAINED_PARENT_NAMESPACE is not None:
  raise ValueError('KERNEL_SOURCE_ENTRY_ONE_RETAINED_ORIGINAL_OWNER_NO_REPLAY')
 verify_sources();module=parent()
 try:
  return module.create_prefix_owner(bindings_path,bindings_sha256,code_root=code_root,factory_path=factory_path,
   factory_manifest=factory_manifest,tester_bindings_path=tester_bindings_path,
   tester_bindings_sha256=tester_bindings_sha256,approved_repair_sources=tuple(approved_repair_sources))
 finally:
  RETAINED_PARENT_NAMESPACE=module.RETAINED_PARENT_NAMESPACE
  RETAINED_PRIVATE_FACTORY=module.RETAINED_PRIVATE_FACTORY
  RETAINED_ORIGINAL_OWNER=module.RETAINED_ORIGINAL_OWNER
  RETAINED_ORIGINAL_LEDGER=module.RETAINED_ORIGINAL_LEDGER


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
 original=parent();module=original.private_emitter(tester_bindings_path=tester_bindings_path,
  tester_bindings_sha256=tester_bindings_sha256)
 root=Path(__file__).resolve().parent
 if module._idle_helper_path!=Path(original.__file__):
  raise ValueError('KERNEL_SOURCE_ENTRY_EXACT_CURRENT_SERVICES_HELPER_BEFORE_NEW_HELPER')
 module._idle_helper_path=Path(__file__).resolve()
 extra=[Path(__file__).resolve(),
  *(root.parent/'formal100m-kernel-control-source-supplement-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1'/name for name in(
    'kernel_control_source_supplement.py','kernel_control_host_restore.py'))]
 module._idle_pin_paths=tuple(dict.fromkeys((*module._idle_pin_paths,*extra)))
 return module


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,
 tester_bindings_sha256=None,new_bindings=None):
 module=parent();original=module.emit
 fn=FunctionType(original.__code__,dict(vars(module),private_emitter=private_emitter),
  original.__name__,original.__defaults__,original.__closure__)
 fn.__kwdefaults__=original.__kwdefaults__
 return fn(bindings_path,bindings_sha256,destination=destination,tester_bindings_path=tester_bindings_path,
  tester_bindings_sha256=tester_bindings_sha256,new_bindings=new_bindings)


def private_namespace(original):
 shared=parent().private_namespace(original);namespace=vars(shared);previous=namespace['command']
 def command(row):
  if type(row)is dict and row.get('op')==OP:
   if set(row)!={'op'}:raise ValueError('KERNEL_SOURCE_ENTRY_ONLY_EXACT_NO_ARGUMENT_OPCODE')
   owner=namespace['RETAINED_OWNER']
   if owner is None:raise ValueError('KERNEL_SOURCE_ENTRY_SAME_RETAINED_SOURCE_OWNER_REQUIRED')
   return publish_kernel(owner)
  return previous(row)
 namespace['command']=command
 shared._kernel_source_previous_command=previous;shared._kernel_source_opcode=OP
 return shared


def original_entry():return parent().original_entry()


def main(argv=None):
 try:return private_namespace(original_entry()).main(argv)
 except Exception as error:
  frames=[];tb=error.__traceback__
  while tb:
   frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
  print(json.dumps(dict(PUBLIC_code='KERNEL_SOURCE_ACTUAL_COLD_CHAIN_ENTRY_REFUSED',exception_type=type(error).__name__,
   locations=frames,message_or_private_body_exported=False),sort_keys=True));return 2


if __name__=='__main__':raise SystemExit(main())
