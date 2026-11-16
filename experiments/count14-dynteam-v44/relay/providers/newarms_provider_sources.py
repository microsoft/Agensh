"""Msg220 prospective formal/isolated390 transport and SYSTEM source ports.

No owner, controller, model, ledger, dispatcher or sampler is constructed by
import/selection. The formal wrapper delegates the whole original validation
and natural/fixed-code/allowance binder first, in a NEW private namespace.
Never install in a running owner or a paid/mid-trajectory cold restore.
"""
from pathlib import Path
from types import FunctionType,ModuleType
from dataclasses import replace
import copy,hashlib,importlib,os,stat
import gateway_pr1_v2 as G

HERE=Path(__file__).resolve().parent
FORMAL='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
ISOLATED390='3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937'
CHILD_INDEX='fc5786144416a8b2e882dc7c3d42da56e344d508f54de8bc31fcbe5e491d5214'
NEWROOT_SELECTOR='591159e113ff0587300bcde96946bc2563592c733deada43da95dcafc8f74057'
ORIGINAL_SAMPLER='f80a9758323acc3e830b0ad48075f5c6cb2b4d5683862f6ab1f67c325819adf3'
NEW_SAMPLER='e584c5d50895110e5b7f4b14b38a30095f8d0f87390129b95ea38b07dff4f7f3'
BOOTSTRAP='33b94ab50a4552b23e868508639a24cc534893aee6c08d7a5e5e9f0b9ec461aa'
SYSTEM='d1b1f6fea69fd90fae229930d5f206669472732ca684f5141e8994438c19ff7c'
_WRAPPED={}

def need(ok,code):G.need(ok,'NEWARMS_'+code)
def frozen(path,pin):
    p=Path(path);s=p.lstat()
    need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
        stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
        stat.S_IMODE(s.st_mode)==0o444 and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
        'EXACT_FROZEN_REGULAR_SOURCE')
    return p.read_bytes()
def scope(contract):
    from common import digest
    G.registered_scope(contract)
    pin=digest(contract)
    need((contract['mode']=='production' and pin==FORMAL)or
         (contract['mode']=='smoke' and pin==ISOLATED390),'ONLY_EXACT_FORMAL_SIX_OR_NEW_ISOLATED390')
    return pin
def verify_children():
    import json
    index=json.loads(frozen(HERE/'PROVIDER_CHILD_TREES_PUBLIC.json',CHILD_INDEX))
    for name,row in index['files'].items():
        path=HERE/name
        need(path.is_relative_to(HERE) and '..'not in Path(name).parts,'EXACT_PRIVATE_CHILD_RELATIVE_PATH')
        need(len(frozen(path,row['sha256']))==row['bytes'],'EXACT_PRIVATE_CHILD_BYTES')
    return index

def validated_bindings(original,*,contract):
    """Called AFTER the original factory validator, never instead of it."""
    scope(contract);verify_children()
    need(type(original)is dict and type(original.get('system_probe'))is dict,
        'ORIGINAL_VALIDATED_PUBLIC_PARAMETER_VIEW')
    result=G.override_bindings(original) # deep copy, exact old provider only
    system=result['system_probe']
    oldchild=original['system_probe']['child'];oldpin=original['system_probe']['child_sha256']
    system['child']=str(HERE/'msg220-system/runtime-v1/native_system_probe_child.py')
    system['child_sha256']=SYSTEM
    inverse=copy.deepcopy(result);inverse['provider']['base_url']=G.OLD_BASE
    inverse['system_probe']['child']=oldchild;inverse['system_probe']['child_sha256']=oldpin
    need(inverse==original,'ONLY_PROVIDER_BASE_AND_REGISTERED_SYSTEM_CHILD_SOURCE_INVERSE')
    return result,dict(G.provider_change(),new_system_child_reference=dict(path=system['child'],sha256=SYSTEM),
        original_factory_validator_must_run_first=True,original_binding_file_not_written=True,
        original_resource_sampler_arguments_unchanged=True,actual_runtime_cutover=None)

def sampler_after_original_selection(original,*,contract):
    """ONLY after the unchanged full original newroot/host/ledger guards."""
    from native_resource_producer import ResourceSamplerSources
    scope(contract);verify_children()
    need(type(original)is ResourceSamplerSources and original.child_sha256==ORIGINAL_SAMPLER and
        original.bootstrap_sha256==BOOTSTRAP,'ORIGINAL_EXACT18_SELECTION_ALREADY_COMPLETED')
    frozen(original.child,ORIGINAL_SAMPLER)
    frozen(Path(original.child).with_name('native_cold_owner_entry.py'),BOOTSTRAP)
    return replace(original,child=HERE/'msg220-sampler/native_resource_sample_child.py',child_sha256=NEW_SAMPLER)

def wrap_private_factory(module):
    """Compose at the CURRENT initial formal loader's existing private seam.

    Caller must freeze this into the complete original cold import map.
    No original/shared module is replaced; module must be a new private copy.
    This does NOT provide the paid-cohort restore required later in 100M.
    """
    need(type(module)is ModuleType and module.create_prefix_owner.__globals__ is vars(module) and
        type(module.private_original_constructor)is FunctionType and
        id(module)not in _WRAPPED and not hasattr(module,'msg220_provider_source_hook'),
        'ONLY_ONE_NEW_ORIGINAL_PRIVATE_FORMAL_FACTORY_NAMESPACE')
    verify_children()
    selector=importlib.import_module('newroot_private_resource_sources')
    frozen(selector.__file__,NEWROOT_SELECTOR) # reject old sampler wiring BEFORE constructor
    previous=module.private_original_constructor
    def constructor(bind_same_owner):
        helper=previous(bind_same_owner)
        need(type(helper)is ModuleType and helper.create_prefix_owner.__globals__ is vars(helper) and
            helper.RETAINED_FACTORY_OWNER is helper.RETAINED_FACTORY_LEDGER is None and
            not hasattr(helper,'msg220_provider_source_hook'),'NEW_ORIGINAL_HELPER_BEFORE_LEDGER_OR_OWNER')
        old_validate=helper.validate_bindings;old_binder=helper._formal_bind_same_owner
        # Private cold source seam: select the REAL controller factory only
        # after all existing binders, but BEFORE normal barrier closes over
        # the bound prepare. No closure/global spoof or late method rebind.
        need(not hasattr(helper,'_msg238_PR1_before_normal_barrier'),
            'NEW_PRIVATE_HELPER_PROVIDER_COLD_SOURCE_SELECTOR_ONCE')
        selected_cohorts=[]
        def before_normal_barrier(cohort):
            need(not selected_cohorts and not hasattr(cohort,'normal_cold_barrier') and
                not hasattr(cohort,'normal_cold_sealer'),
                'EXACT_ORIGINAL_PREPARE_BEFORE_NORMAL_BARRIER_AND_SEALER_ONCE')
            selected_cohorts.append(cohort) # retain partial; never retry a failed hook
            from formal_pr1_dispatch import install_new_cohort
            install_new_cohort(cohort,package_directory=HERE)
        helper._msg238_PR1_before_normal_barrier=before_normal_barrier
        def validate(value,*,code_root):
            checked=old_validate(value,code_root=code_root) # every original scope/pin/template/provider guard
            c=checked['contract']
            from formal_public_common import read_contract
            contract=read_contract(helper,c,code_root=code_root)
            need(scope(contract)==FORMAL,'FORMAL_FACTORY_NOT_A_SMOKE_OR_PAID_RESTORE_OVERRIDE')
            selected,proof=validated_bindings(checked,contract=contract)
            helper.msg220_provider_source_selection=proof
            return selected
        def bind(owner,*,sources):
            cohort=old_binder(owner,sources=sources) # original SDK/fixed/allowance/natural first, exactly once
            core=owner.core
            need(core.resource_producer.sources.child_sha256==NEW_SAMPLER and
                Path(core.resource_producer.sources.child)==HERE/'msg220-sampler/native_resource_sample_child.py',
                'ORIGINAL_NEWROOT_CONSTRUCTOR_SELECTED_NEW_FINITE_CHILD')
            actual=G.install_new_producer(core) # original full unpaid/new-owner/zero-request guards
            need(len(selected_cohorts)==1 and selected_cohorts[0] is cohort and
                helper._msg238_PR1_before_normal_barrier is before_normal_barrier and
                hasattr(cohort,'msg220_provider_child_source') and
                hasattr(cohort,'normal_cold_barrier') and hasattr(cohort,'normal_cold_sealer'),
                'REAL_PROVIDER_FACTORY_SELECTED_BEFORE_COMPLETE_ORIGINAL_NORMAL_COLD_BIND')
            # Only a genuinely constructed core can publish an actual config
            # selection. Not a fake request, activation, health or fee event.
            from common import publish,wire
            home=Path(core.home)/'provider-change-msg220'
            need(home.parent.resolve()==home.parent and not os.path.lexists(home),'NEW_OWNER_PROVIDER_METADATA_DIRECTORY_ONCE')
            home.mkdir(mode=0o700)
            publish(home/'INTENT_PUBLIC.json',wire(helper.msg220_provider_source_selection),mode=0o444)
            publish(home/'ACTUAL_CONFIG_PUBLIC.json',wire(dict(actual,new_SYSTEM200=None,original_validator=None,ACTIVATE=None)),mode=0o444)
            return cohort
        helper.validate_bindings=validate;helper._formal_bind_same_owner=bind
        helper.msg220_provider_source_hook=dict(original_create_prefix_owner_CodeType_unchanged=True,
            original_validation_and_whole_existing_binder_execute_first=True,
            SEARCH_SYSTEM_AUX_selected_only_for_new_initial_formal_owner=True,
            actual_runtime_qualified=False,formal_delivery=False)
        return helper
    _WRAPPED[id(module)]=module
    module.private_original_constructor=constructor
    module.msg220_provider_source_hook=dict(schema='count14-msg220-new-initial-formal-private-factory-source-hook-v1',
        whole_source_import_map_and_related_qualification_required=True,
        existing_factory_code_and_cold_protocol_not_replaced=True,
        actual_factory_or_owner_or_paid_runtime_created=False,formal_delivery=False)
    return module
