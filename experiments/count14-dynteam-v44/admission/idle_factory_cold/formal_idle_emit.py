#!/usr/bin/env python3
"""Private emitter path/map seam; same prior formal schema/guards/entry."""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
import textwrap
sys.path.insert(0,str(Path(__file__).resolve().parent))

EMITTER_SHA='f6f7a672936c2a73b49cea5b118d989cea32d38d9dd9f981619d9b24361d64e6'


def need(ok,code):
    if not ok:raise ValueError(code)


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    root=Path(__file__).resolve().parent
    path=root.parent/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/formal_public_emit.py'
    need(path.resolve()==path and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==EMITTER_SHA,
         'FORMAL_IDLE_PRIOR_EXACT_FORMAL_EMITTER_PIN')
    spec=importlib.util.spec_from_file_location('count14_formal_private_idle_emitter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=module.emit;prior=ast.parse(textwrap.dedent(inspect.getsource(original)));tree=copy.deepcopy(prior)
    changes=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='helper_path':
            changes.append((node,copy.deepcopy(node)));node.value=ast.Name(id='_idle_helper_path',ctx=ast.Load())
        if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='path' and isinstance(node.iter,ast.Tuple):
            changes.append((node,copy.deepcopy(node)));node.iter=ast.Name(id='_idle_pin_paths',ctx=ast.Load())
    source_nodes=[n for n in ast.walk(tree)if isinstance(n,ast.Assign)and len(n.targets)==1 and
        isinstance(n.targets[0],ast.Name)and n.targets[0].id=='source'and isinstance(n.value,ast.Constant)and isinstance(n.value.value,str)]
    need(len(source_nodes)==1,'FORMAL_TESTER_ONE_ORIGINAL_EMITTED_FACTORY_SOURCE_STRING')
    node=source_nodes[0];old=copy.deepcopy(node)
    target='factory_path=Path(__file__).resolve(),factory_manifest=Path(@MANIFEST@))'
    need(node.value.value.count(target)==1,'FORMAL_TESTER_ONE_ORIGINAL_GENERATED_CREATE_CALL')
    replacement=target[:-1]+',tester_bindings_path='+repr(None if tester_bindings_path is None else str(Path(tester_bindings_path)))+\
        ',tester_bindings_sha256='+repr(tester_bindings_sha256)+')'
    node.value.value=node.value.value.replace(target,replacement);changes.append((node,old))
    need(len(changes)==3,'FORMAL_IDLE_EMITTER_HELPER_PINSET_AND_EXPLICIT_COMPANION_ONLY')
    reverted=copy.deepcopy(tree)
    for new,old in changes:
        matches=[n for n in ast.walk(reverted)if type(n)is type(new)and ast.dump(n,include_attributes=False)==ast.dump(new,include_attributes=False)]
        need(len(matches)==1,'FORMAL_IDLE_EMITTER_UNIQUE_INVERSE_SELECTOR')
        matches[0].__dict__.update(copy.deepcopy(old.__dict__))
    need(ast.dump(reverted,include_attributes=False)==ast.dump(prior,include_attributes=False),
         'FORMAL_IDLE_ALL_OTHER_EMISSION_AND_SCHEMA_GUARDS_UNCHANGED')
    helper=root/'formal_idle_factory.py'
    module._idle_helper_path=helper
    module._idle_pin_paths=(helper,Path(__file__).resolve(),root/'formal_idle_installer.py',
        root.parent/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/formal_public_common.py')
    exec(compile(ast.fix_missing_locations(tree),__file__+':private-path-only-seam','exec'),module.__dict__)
    module._idle_emitter_proof=dict(original_emitter_sha256=EMITTER_SHA,reverse_AST_equal=True,selectors=3,
        explicit_tester_companion_not_Game_scope=True)
    return module


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,tester_bindings_sha256=None):
    from formal_public_factory import base_helper
    guard=base_helper();binding=guard.public(bindings_path,bindings_sha256)
    if binding.get('template_only')is False:
        need(tester_bindings_path is not None and tester_bindings_sha256 is not None,
             'FORMAL_TESTER_REAL_FACTORY_EMISSION_REQUIRES_PUBLIC_COMPANION')
    need((tester_bindings_path is None)==(tester_bindings_sha256 is None),
         'FORMAL_TESTER_COMPANION_PATH_AND_PIN_MUST_BE_PAIRED')
    module=private_emitter(tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
    value=module.emit(bindings_path,bindings_sha256,destination=destination)
    from formal_public_common import save
    provenance=save(Path(destination)/'NATIVE_IDLE_COLD_BINDING_PUBLIC.json',dict(
        schema='count14-formal-native-idle-cold-factory-WIP-v1',
        installation_order=['same original bind_formal_cohort','original native idle watchdog','original terminal source/retirement'],
        prior_control_plan_remaining_flag_is_not_runtime_qualification=True,
        native_idle_factory_hook_implemented=True,real_native_metadata_tick_qualified=False,
        tester_binding_before_prepare_and_after_host_cold_seams=True,
        actual_six_scope_companion_required_before_real_create=True,first_formal_natural_point_K3_remaining=True,
        zero_live_without_pending_no_forced_spawn=True,owner_created=False,models=0,formal_delivery=False))
    value.update(native_idle_cold_provenance=provenance,native_idle_watchdog_cold_factory_bound=True,formal_delivery=False,
        first_formal_natural_point_K3_remaining=True,zero_live_without_pending_no_forced_spawn=True)
    return value


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--bindings',required=True);p.add_argument('--bindings-sha256',required=True)
    p.add_argument('--destination',required=True);p.add_argument('--tester-bindings');p.add_argument('--tester-bindings-sha256');a=p.parse_args(argv)
    try:
        print(json.dumps(emit(a.bindings,a.bindings_sha256,destination=a.destination,
            tester_bindings_path=a.tester_bindings,tester_bindings_sha256=a.tester_bindings_sha256),sort_keys=True));return 0
    except Exception as error:
        locations,tb=[],error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_IDLE_COLD_EMITTER_REFUSED',exception_type=type(error).__name__,locations=locations),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
