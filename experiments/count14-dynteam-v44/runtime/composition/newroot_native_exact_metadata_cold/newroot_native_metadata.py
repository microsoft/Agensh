"""Approved a892 exact control bind + optional StopSignal, genuine NEW owners.

Original class/module sources stay unchanged. No old graph, hot replacement,
container action, replay, finance/schema change or relaxed explicit signal.
"""
from pathlib import Path
from types import MethodType
import hashlib,importlib.util,os,stat

HERE=Path(__file__).resolve().parent
INSPECT=('optional_stop_signal_inspect.py','cacd7212719442bf0886a4fb1e6485ff7a5591e1c3f6e7111bb44b997e7f734e')
VALIDATOR=('native_exact_control_bind.py','54ee9dd7eb09268ca86ac6f7ca43153ddc0d1fd5e22572a830801515de166fe2')
FORMAL='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
RACING='3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937'
_RETAINED={}
def need(ok):
    if not ok:raise ValueError('NEWROOT_OPTIONAL_NATIVE_METADATA_ONLY_GENUINE_EMPTY_HELD_NEW_OWNER')
def load(ref):
    p=HERE/ref[0];s=p.lstat()
    need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and
         s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and hashlib.sha256(p.read_bytes()).hexdigest()==ref[1])
    spec=importlib.util.spec_from_file_location('count14_newroot_original_'+p.stem,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def scope(core):
    from common import digest
    c=core.contract
    if core.qualification_only:
        need(os.uname().nodename!='H100DEV4'and
             getattr(core.ledger,'_dynteam_qualification_only',None)is True and
             any(p.startswith('OWN-')for p in Path(core.home).parts))
    elif c['mode']=='production':
        need(digest(c)==FORMAL and len(core.rows)==6 and
             {(r['arm'],r['block'])for r in core.rows.values()}=={(a,b)for a in('DYNTEAM','DYNTEAM_RACING')for b in(1,2,3)})
    else:
        need(c['mode']=='smoke'and digest(c)==RACING and len(core.rows)==2 and
             tuple(a['root']for a in c['arms'])==('/mnt/ptb-scratch2/ct14-dtr-smoke-20261105/u','/mnt/ptb-scratch2/ct14-dtr-smoke-20261105/r'))
    return True
def bind_new_owner(owner):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from native_container_retirement import NativeContainerRegistry
    from native_cold_bootstrap import NativeColdBootstrap
    from native_docker_scope import ScopedDocker
    from native_peer_registry import process_birth
    need(type(owner)is NativeColdOwner and not owner.errors and type(owner.core)is OriginalRelayCore and
         owner.ledger is owner.core.ledger and type(owner.bootstrap)is NativeColdBootstrap and
         owner.bootstrap.core is owner.core and not owner.bootstrap.records and id(owner)not in _RETAINED)
    core=owner.core;scope(core);owner.zero_model_prefix()
    registry=core.native_containers
    need(not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held)==set(core.rows)and not core.peers._peers and
         type(registry)is NativeContainerRegistry and registry.core is core and type(registry.docker)is ScopedDocker and
         not registry.records and not registry.boot_plans and not registry.bootstrap_busy and not registry.bootstrap_failures and
         'validate'not in vars(registry)and 'inspect'not in vars(registry.docker)and
         not core.ledger.mutex._is_owned())
    with core.ledger.mutex:
        need(all(core.ledger.db.execute('SELECT COUNT(*) FROM '+n).fetchone()[0]==0
                 for n in('requests','unknown_charges','aux_scopes','aux_permits','snapshots','acks','unknown_stops'))and
             core.ledger.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0]==1 and
             not core.ledger.memory_faults)
        before=core.ledger.db.total_changes
    # Compile and verify both source inverses BEFORE the first binding.
    inspect=load(INSPECT);validator=load(VALIDATOR)
    import native_container_retirement as original
    whitelist=validator.FrozenControls(core)
    function,proof=validator.compile_validate(whitelist)
    record=dict(owner=owner,birth=process_birth(os.getpid()),phase='PARTIAL_RETAINED_NO_RETRY',whitelist=whitelist,validator_module=validator,writer_attempted=False)
    _RETAINED[id(owner)]=record
    projected=inspect.select_private_inspect(registry.docker)
    registry.validate=MethodType(function,registry)
    need(core.ledger.db.total_changes==before and not registry.records and not registry.boot_plans and not core.peers._peers)
    owner.zero_model_prefix();record['phase']='BOUND_NEW_EMPTY_PRIVATE_METADATA_METHODS'
    record['proof']=dict(schema='count14-newroot-native-optional-signal-and-exact-control-bind-bound-v2',
        original_inspect_projection=projected,original_validator_selection=proof,
        original_class_and_module_methods_sources_unchanged=True,raw_missing_optional_value_remains_null=True,
        approved_exact_bind_plan_sha256=validator.APPROVED_PLAN,
        frozen_original_SDK_role_directory_whitelist_before_first_native_action=True,
        original_agent_control_RO_and_clock_RO_preserved=True,
        explicit_nondefault_signals_still_refused=True,only_this_new_empty_registry_and_docker_instance=True,
        financial_writes_or_replay_or_container_actions_or_models=0)
    return record['proof']


def bind_checkpoint_consumers(owner):
    record=_RETAINED.get(id(owner))
    need(record is not None and record['owner']is owner and
         record['phase']=='BOUND_NEW_EMPTY_PRIVATE_METADATA_METHODS'and record['writer_attempted']is False)
    scope(owner.core);record['writer_attempted']=True
    order=load(('newroot_prerelease_order.py','5a38248395aa5f9b67e0f2991302b7bd5b972a93c14f5b1521488589dc42aefd'))
    mattermost=load(('future_native_mmvolume.py','a611121c5cc4300cb64c79acd849c1c47b83995a8895129efe9ba728b522bc57'))
    module=load(('newroot_native_writer.py','72e4adc7fcc3da18a69f801f95003e44389a6a40e54dc16211e3094637a75c2c'))
    result=module.bind_science(owner,whitelist=record['whitelist'],
        control_module=record['validator_module'],scope_guard=scope,prerelease_order=order,mattermost_module=mattermost)
    record['writer_proof']=result
    record['writer_module']=module
    return result


def require_checkpoint_consumers_bound(owner):
    """Post-binder assertion only; NEVER bind a second time after cold hooks."""
    record=_RETAINED.get(id(owner))
    need(record is not None and record['owner']is owner and
         record['phase']=='BOUND_NEW_EMPTY_PRIVATE_METADATA_METHODS'and
         record['writer_attempted']is True and 'writer_proof'in record and
         'writer_module'in record and not owner.errors)
    scope(owner.core)
    return record['writer_proof']


def checkpoint_prepare_source_for_tester(cohort):
    owner=cohort.owner
    require_checkpoint_consumers_bound(owner)
    need(owner.scientific_smoke is cohort and cohort.core is owner.core)
    return _RETAINED[id(owner)]['writer_module'].tester_prepare_source(owner)
