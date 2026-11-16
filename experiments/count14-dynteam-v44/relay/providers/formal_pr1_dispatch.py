"""Cold-only selection of msg220's qualified formal AUX child.

Compose AFTER the original fixed-code/allowance/natural cohort binders. Never
replace their controller/prepare/dispatch bodies or an already-paid graph.
Only this new scope/dispatcher instance's child entry and pin change.
"""
from pathlib import Path
from types import FunctionType,MethodType
import hashlib,os,stat

CONTRACT='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
ENTRY_PIN='afc9847cdc495cce88e4eb63568b5d977a4ace3c98ba3b36dca2c492eab4931a'
OPTIONS_PIN='5d4dd236a30166e7257f6853f4fe7d9cb10c84aa3ebeb337745184910713a1a7'
NATURAL_CHILD_PIN='f6e32964856b6516342075ae352ea00f23015a7b674facd61306162b9c5f6e66'
APPROVED_CHILD_PIN='983f8aa0517b895355376a5f41d36b0b907f2cdc86556bc811354ee5740837ed'
PARENTS={
 'formal100m-scope-wip-v1/formal_final_child.py':'9bfa1bbb0a5a8b677c956e3d7c0ce577a575f20f569ae0c4ba41417ccf2af0b6',
 'formal100m-allowance-native-wip-v1/allowance_final_child.py':'e4384eeb3f277ef779de76bc1f7998068f9320b46ee109181fc965bc28bfa8af',
 'formal100m-allowance-queue-proposal-v1/queue_child.py':'5c99227268367fb77ceb161968cfe9860733613906c8649ba773e4f759aadf66',
}
_ATTEMPTS={}

def need(ok,code):
    if not ok:raise ValueError('MSG220_FORMAL_DISPATCH_'+code)

def frozen(path,pin):
    p=Path(path);s=p.lstat()
    need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
         not stat.S_IMODE(s.st_mode)&0o222 and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
         'EXACT_FROZEN_SOURCE')
    return p

def verify_sources(package_directory):
    home=Path(package_directory)
    entry=frozen(home/'formal_pr1_final_child.py',ENTRY_PIN)
    frozen(home/'formal_provider_options.py',OPTIONS_PIN)
    return entry

def augment_scope(scope,*,package_directory):
    from formal_runtime import FormalFinalRuntimeScope
    from native_final_dispatch import NativeFinalDispatcher
    from common import hash_file
    need(type(scope) is FormalFinalRuntimeScope and scope.sha==CONTRACT and
         hasattr(scope,'formal_natural_sidecar') and not hasattr(scope,'msg220_provider_child_source'),
         'NEW_EXACT_ALREADY_NATURAL_FORMAL_SCOPE_ONLY')
    entry=verify_sources(package_directory);root=entry.parent.parent
    before=scope.dispatcher
    need(type(before) is MethodType and before.__self__ is scope,'ORIGINAL_BOUND_DISPATCHER_FACTORY')
    def dispatcher(own,*args,**kwargs):
        value=before(*args,**kwargs) # full original typed queue/capacity/failure path first
        need(type(value) is NativeFinalDispatcher and not value.children and not value.points and
             value.faulted is False and not hasattr(value,'msg220_provider_child_source'),
             'JUST_CONSTRUCTED_ORIGINAL_DISPATCHER_NO_JOBS_OR_LATE_REENTRY')
        old=frozen(root/'formal100m-queue-approved-cold-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/approved_queue_child.py',APPROVED_CHILD_PIN)
        need(value.entry==old and hash_file(old)==value.entry_pin,'ORIGINAL_APPROVED_CARRIER_ENTRY_NOT_OTHER_STAGE')
        need(hasattr(scope,'approved_carrier_domain') and
             getattr(value,'formal_approved_carrier_domain',None) is scope.approved_carrier_domain,
             'ORIGINAL_SAME_APPROVED_CARRIER_DOMAIN_RETAINED')
        parent=Path(value.environment['COUNT14_NATURAL_PARENT_CHILD'])
        relative=parent.relative_to(root).as_posix()
        need(relative in PARENTS and value.environment['COUNT14_NATURAL_PARENT_CHILD_SHA256']==PARENTS[relative],
             'ORIGINAL_PARENT_ALLOWANCE_QUEUE_SELECTION_PRESERVED')
        frozen(parent,PARENTS[relative])
        value.entry=entry;value.entry_pin=hash_file(entry)
        value.msg220_provider_child_source=dict(path=str(entry),sha256=ENTRY_PIN,
            original_parent_child=str(parent),original_parent_child_sha256=PARENTS[relative],
            only_new_child_entry_and_pin_changed=True,actual_AUX_request=None)
        return value
    scope.dispatcher=MethodType(dispatcher,scope)
    scope.msg220_provider_child_source=dict(path=str(entry),sha256=ENTRY_PIN)
    return scope

def _clone(function,**values):
    result=FunctionType(function.__code__,dict(function.__globals__,**values),function.__name__,
        function.__defaults__,function.__closure__)
    result.__kwdefaults__=function.__kwdefaults__
    need(result.__code__ is function.__code__,'COMPLETE_ORIGINAL_PREPARE_CODETYPE')
    return result

def select_controller_factory(original,*,package_directory):
    """Select after existing natural/fixed-code wrappers, without calling it."""
    verify_sources(package_directory)
    need(type(original) is FunctionType,'EXACT_CURRENT_PRIVATE_FACTORY_FUNCTION')
    def factory(*args,**kwargs):
        controller=original(*args,**kwargs)
        before=controller._prepare.__func__
        previous_scope=before.__globals__['SmokeFinalRuntimeScope']
        def scope(*a,**k):
            return augment_scope(previous_scope(*a,**k),package_directory=package_directory)
        controller._prepare=MethodType(_clone(before,SmokeFinalRuntimeScope=scope),controller)
        return controller
    return factory

def install_new_cohort(cohort,*,package_directory):
    """Not a paid restore: only a never-released genuine new formal cohort."""
    from native_formal_cohort import NativeFormalCohort
    from original_relay_core import OriginalRelayCore
    from native_cold_owner import NativeColdOwner
    from native_peer_registry import process_birth
    from common import digest
    need(type(cohort) is NativeFormalCohort,'EXACT_FORMAL_COHORT_BEFORE_ATTRIBUTES')
    core,owner=cohort.core,cohort.owner
    need(type(core) is OriginalRelayCore and type(owner) is NativeColdOwner and
         owner.core is core and owner.scientific_smoke is cohort and not owner.errors and
         digest(core.contract)==CONTRACT and cohort.birth==process_birth(os.getpid()) and
         not core.qualification_only and not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held)==set(core.rows) and
         cohort.state=='PREPARING_ORIGINAL_SIX_HELD' and
         hasattr(cohort,'formal_natural_cold_proof') and
         not hasattr(cohort,'msg220_provider_child_source') and id(cohort) not in _ATTEMPTS,
         'ONLY_NEW_SAME_OWNER_AFTER_ORIGINAL_NATURAL_BIND_BEFORE_SCIENCE')
    need(set(cohort.tracks)==set(core.rows) and all(
         row['state']=='BOUND_AWAIT_ORIGINAL_SOURCE' and row['task_attempted'] is False and
         row['gate_released'] is False and row['failure'] is None for row in cohort.tracks.values()),
         'ALL_SIX_REAL_TRACKS_UNRELEASED_NO_PARTIAL_ADOPTION')
    with core.ledger.mutex:
        need(all(core.ledger.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]==0
                 for name in ('requests','unknown_charges','aux_scopes','aux_permits')),
             'ZERO_SCIENCE_UNKNOWN_AND_AUX_NO_RESET')
    current=cohort._prepare_one.__func__
    selected=select_controller_factory(current.__globals__['create_formal_final_controller'],package_directory=package_directory)
    _ATTEMPTS[id(cohort)]=dict(cohort=cohort,state='BINDING_RETAIN_NO_RETRY')
    cohort._prepare_one=MethodType(_clone(current,create_formal_final_controller=selected),cohort)
    cohort.msg220_provider_child_source=dict(schema='count14-msg220-new-formal-cohort-AUX-child-source-v1',
        entry=str(Path(package_directory)/'formal_pr1_final_child.py'),entry_sha256=ENTRY_PIN,
        original_prepare_CodeType_and_all_prior_factory_wrappers_retained=True,
        original_natural_allowance_queue_parent_routes_preserved=True,
        actual_runtime_qualification=False,formal_delivery=False)
    _ATTEMPTS[id(cohort)]['state']='NEW_SOURCE_SELECTED_NOT_SCIENTIFIC_AUTHORITY'
    return cohort.msg220_provider_child_source
