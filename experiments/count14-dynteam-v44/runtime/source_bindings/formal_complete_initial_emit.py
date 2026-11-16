"""Frozen formal initial-factory composition: complete retained finite child.

Original full constructor/exact18/PR1/binders execute FIRST. Only initial
unspent dependency fields are selected before the first resource poll, never
an existing owner/actor or target RAM. No dispatcher, probe, fee or SQL change.
"""
from pathlib import Path
from types import FunctionType
from dataclasses import replace
import argparse
import hashlib
import importlib.util
import json
import os
import stat

HERE=Path(__file__).resolve().parent
FORMAL='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
PREVIOUS=('formal-provider-msg220221-initial-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-indexsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_provider_initial_emit.py','cb0d4a8249c426bd1dcc524fe58bf9ac8ff7e3ec2ef100b5961eee162bd031be')
OLD_CHILD='e584c5d50895110e5b7f4b14b38a30095f8d0f87390129b95ea38b07dff4f7f3'
BOOTSTRAP='33b94ab50a4552b23e868508639a24cc534893aee6c08d7a5e5e9f0b9ec461aa'
CHILD='e537afda47787be23d5af8e2eb7b11c0698faa12c84bd97e65d741e5b982ca0a'
CHILD_INDEX='664580301b83fc5c3360a36883ee0a302309e0e687bcd4f98526c99f97b9fbee'
_PARENT=None
_INSTALLED=set()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen(path,pin):
    p=Path(path);s=p.lstat()
    if not(p.is_absolute() and p.resolve()==p and not p.is_symlink() and stat.S_ISREG(s.st_mode)
           and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and stat.S_IMODE(s.st_mode)==0o444
           and sha(p)==pin):
        raise ValueError('FORMAL_COMPLETE_INITIAL_EXACT_FROZEN_SOURCE')
    return p


def clone(fn,**bindings):
    f=FunctionType(fn.__code__,dict(fn.__globals__,**bindings),fn.__name__,fn.__defaults__,fn.__closure__)
    f.__kwdefaults__=fn.__kwdefaults__
    return f


def previous():
    global _PARENT
    path=frozen(HERE.parent/PREVIOUS[0],PREVIOUS[1])
    if _PARENT is None:
        spec=importlib.util.spec_from_file_location('formal_complete_previous_full_provider_emitter',path)
        _PARENT=importlib.util.module_from_spec(spec);spec.loader.exec_module(_PARENT)
    return _PARENT


def child_files():
    home=HERE/'complete-sampler-formal'
    index=json.loads(frozen(home/'COMPLETE_SAMPLER_SOURCE_PUBLIC.json',CHILD_INDEX).read_bytes())
    for name,pin in index['files'].items():
        assert Path(name).name==name
        frozen(home/name,pin)
    assert index['files']['native_resource_sample_child.py']==CHILD
    assert index['files']['native_cold_owner_entry.py']==BOOTSTRAP
    return home,index


def select_complete_initial_dependency(core):
    from common import need,digest,publish,wire
    from original_relay_core import OriginalRelayCore
    from native_resource_producer import NativeResourceProducer,ResourceSamplerSources
    from native_peer_registry import process_birth
    need(type(core)is OriginalRelayCore and not core.qualification_only and not core.closed and
         digest(core.contract)==FORMAL and len(core.rows)==6 and not core.scientific_activation_qualified and
         not core.errors and not core.ledger.memory_faults and set(core.gate.startup_held)==set(core.rows),
         'FORMAL_COMPLETE_ONLY_NEW_UNRELEASED_SIX_CORE')
    producer=core.resource_producer
    need(type(producer)is NativeResourceProducer and type(producer.sources)is ResourceSamplerSources and
         producer.owner==process_birth(os.getpid()) and producer.sequence==0 and not producer.records and
         not producer.failures and producer.next_due==0 and producer.accepting and id(producer)not in _INSTALLED,
         'FORMAL_COMPLETE_BEFORE_FIRST_POLL_NO_REPLACEMENT_OR_RETRY')
    with core.ledger.mutex:
        need(all(core.ledger.db.execute('SELECT COUNT(*) FROM '+n).fetchone()[0]==0
                 for n in ('requests','unknown_charges','aux_scopes','aux_permits','snapshots','acks')),
             'FORMAL_COMPLETE_BEFORE_SCIENCE_UNKNOWN_AUX_SNAPSHOT_ONLY')
    old=producer.sources
    expected=HERE.parent/'provider-gateway-pr1-msg221-sources-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-indexsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/msg220-sampler/native_resource_sample_child.py'
    need(old.child==expected and old.child_sha256==OLD_CHILD and old.bootstrap_sha256==BOOTSTRAP,
         'FORMAL_COMPLETE_ORIGINAL_EXACT18_AND_PR1_CHILD_AUTHENTICATED_FIRST')
    frozen(old.child,OLD_CHILD);frozen(old.child.with_name('native_cold_owner_entry.py'),BOOTSTRAP)
    home,index=child_files()
    new=replace(old,child=home/'native_resource_sample_child.py',child_sha256=CHILD)
    need(replace(new,child=old.child,child_sha256=old.child_sha256)==old and
         producer.argv==(str(old.python),'-I','-B',str(old.child)),
         'FORMAL_COMPLETE_ONLY_CHILD_PATH_SHA_TWO_FIELDS_INVERSE')
    old_poll=producer.poll
    producer.sources=new
    producer.argv=(*producer.argv[:-1],str(new.child))
    need(producer.poll is old_poll and producer.argv[:-1]==(str(old.python),'-I','-B'),
         'FORMAL_COMPLETE_ORIGINAL_OWN_TIMING_POLL_AND_PYTHON_ARGS_UNCHANGED')
    _INSTALLED.add(id(producer))
    result=dict(schema='msg236-formal-complete-initial-finite-child-selection-v1',
        original_authenticated_child_sha256=OLD_CHILD,selected_child=str(new.child),selected_child_sha256=CHILD,
        selected_bootstrap_sha256=BOOTSTRAP,full_contract_sha256=FORMAL,
        original_exact18_PR1_and_full_formal_binder_executed_first=True,
        sequence=producer.sequence,records=len(producer.records),producer_argv=list(producer.argv),
        original_poll_object_unchanged=True,retained_native_books=26,retained_SYSTEM_roots=10,
        original_25s_collection_55s_deadline_600s_health_and_nan_rules_unchanged=True,
        actual_child_result_or_validator_or_ACTIVATE=None)
    publish(Path(core.home)/'resources/COMPLETE_INITIAL_CHILD_SELECTION_PUBLIC.json',wire(result),mode=0o444)
    return result


def select_new_formal_factory(factory):
    selected=previous().select_new_formal_factory(factory)
    old=selected.private_original_constructor
    def constructor(bind_same_owner):
        helper=old(bind_same_owner)
        assert helper.RETAINED_FACTORY_OWNER is helper.RETAINED_FACTORY_LEDGER is None
        original=helper._formal_bind_same_owner
        def bind(owner,**kwargs):
            cohort=original(owner,**kwargs)  # all original guards/binders/provider first
            select_complete_initial_dependency(owner.core)
            return cohort
        helper._formal_bind_same_owner=bind
        return helper
    selected.private_original_constructor=constructor
    return selected


def select_new_source_module(module,level=0):
    p=previous()
    return clone(p.select_new_source_module,select_new_formal_factory=select_new_formal_factory,
                 select_new_source_module=select_new_source_module)(module,level)


def insert_selection(original):
    p=previous();selected=p.insert_selection(original)
    code=selected.__code__;values=list(code.co_consts)
    sites=[(i,s)for i,s in enumerate(values)if type(s)is str and
           s.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
    assert len(sites)==1
    i,before=sites[0]
    old_path,new_path=str(Path(p.__file__).resolve()),str(Path(__file__).resolve())
    old_pin,new_pin=PREVIOUS[1],sha(new_path)
    assert before.count(old_path)==before.count(old_pin)==1
    after=before.replace(old_path,new_path,1).replace(old_pin,new_pin,1)
    assert after.replace(new_path,old_path,1).replace(new_pin,old_pin,1)==before
    values[i]=after;updated=code.replace(co_consts=tuple(values))
    assert updated.co_code==code.co_code and updated.replace(co_consts=code.co_consts)==code
    value=FunctionType(updated,selected.__globals__,selected.__name__,selected.__defaults__,selected.__closure__)
    value.__kwdefaults__=selected.__kwdefaults__
    return value


def provider_pin_paths():
    home,index=child_files()
    return tuple(dict.fromkeys((*previous().provider_pin_paths(),Path(__file__).resolve(),
        *(home/n for n in index['files']if Path(n).suffix in ('.py','.js','.mjs')))))


def compiled_emit():
    return clone(previous().compiled_emit,insert_selection=insert_selection,
                 provider_pin_paths=provider_pin_paths)()


def emit_formal(bindings_path,bindings_sha256,**kwargs):
    return clone(previous().emit_formal,compiled_emit=compiled_emit)(bindings_path,bindings_sha256,**kwargs)


def main(argv=None):
    p=argparse.ArgumentParser()
    for n in ('bindings','bindings-sha256','ram-bindings-destination','factory-destination'):
        p.add_argument('--'+n,required=True)
    p.add_argument('--tester-bindings');p.add_argument('--tester-bindings-sha256')
    a=p.parse_args(argv)
    value=json.loads(Path(a.bindings).read_bytes())
    descriptor=value['framework_import_pins']
    reg=json.loads(frozen(descriptor['path'],descriptor['sha256']).read_bytes())
    assert value['code_root']==str(HERE.parent)==reg['code_root'] and value['template_only']is False
    import sys
    sys.path[:0]=[r['path']for r in reg['roots']]
    result=emit_formal(a.bindings,a.bindings_sha256,ram_bindings_path=a.ram_bindings_destination,
        destination=a.factory_destination,tester_bindings_path=a.tester_bindings,
        tester_bindings_sha256=a.tester_bindings_sha256)
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
