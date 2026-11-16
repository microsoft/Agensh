"""Msg210 writer on new formal-six/isolated390 ORIGINAL checkpoint instances.

No original module/class changes, no new owner/supervisor/container, and no
scientific bodies are consumed here. The ordinary preexisting constructor is
called first and the same original checkpoint object is privately bound.
"""
from pathlib import Path
from types import FunctionType, MethodType
import ast, hashlib, inspect, os, textwrap

PLAN='748ed49a3a96665a47044ddf793bb33502a87df715fb7ce3884676776859bd0f'
WRITER_COMPONENT='adcff8375c63ff138ba91e268e906d3937a3fce8423004dbe6badf525bd35139'
FORMAL_COHORT='7a38d82988e3c60181ece17e541c4c86c644ce160dfedba66fe235d5d03b7723'
RACING_SMOKE='72a302960d4e6783c1ee1d8cc87ee75073d067c8e68802375c44466b68ebaf27'
ORDER_COMPONENT='5a38248395aa5f9b67e0f2991302b7bd5b972a93c14f5b1521488589dc42aefd'
RETAINED={}


def need(ok):
    if ok is not True:raise ValueError('NEWROOT_MSG210_EXACT_ORIGINAL_UNUSED_CHECKPOINT_CONSUMER')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bind_science(owner,*,whitelist,control_module,scope_guard,prerelease_order,mattermost_module):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from native_dynamic_checkpoint import DynamicCheckpointPorts
    import native_dynamic_checkpoint as DC,native_dynamic_writer as DW
    import native_exact_control_writer as EW
    need(sha(EW.__file__)==WRITER_COMPONENT and type(owner)is NativeColdOwner and
         type(owner.core)is OriginalRelayCore and owner.ledger is owner.core.ledger and
         not owner.errors and id(owner)not in RETAINED and callable(scope_guard)and scope_guard(owner.core)is True)
    need(sha(prerelease_order.__file__)==ORDER_COMPONENT)
    core=owner.core;science=getattr(owner,'scientific_smoke',None)
    need(science is not None and science.owner is owner and science.core is core and
         whitelist.core is core and whitelist.registry is core.native_containers and
         not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held)==set(core.rows)and not core.ledger.mutex._is_owned())
    with core.ledger.mutex:
        need(core.ledger.db.execute('SELECT COUNT(*)FROM requests').fetchone()[0]==0 and
             core.ledger.db.execute('SELECT COUNT(*)FROM unknown_charges').fetchone()[0]==0 and
             core.ledger.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0]==1)
        changes=core.ledger.db.total_changes
    if core.contract['mode']=='production':
        import native_formal_cohort as N
        need(sha(N.__file__)==FORMAL_COHORT and type(science)is N.NativeFormalCohort and
             science.state=='PREPARING_ORIGINAL_SIX_HELD'and science.failure is None and science.final is None and
             len(science.tracks)==6 and all(r['checkpoint']is None and r['state']=='BOUND_AWAIT_ORIGINAL_SOURCE'
                 for r in science.tracks.values()))
        order_mode='formal'
        method_name='_prepare_one';constructor_name='create_formal_checkpoint_ports'
        original_class=N.NativeFormalCohort
    else:
        import native_racing_smoke as N
        need(sha(N.__file__)==RACING_SMOKE and type(science)is N.NativeRacingSmoke and
             science.state=='BOUND_AWAIT_ORIGINAL_SOURCE'and science.failure is None and
             science.checkpoint is science.final is science.launch is None and
             core.rows[science.t]['arm']=='DYNTEAM_RACING'and len(core.rows)==2)
        order_mode='racing'
        method_name='prepare_tick';constructor_name='racing_checkpoint';original_class=N.NativeRacingSmoke
    method=getattr(science,method_name)
    need(type(method)is MethodType and method.__self__ is science and
         method.__func__.__code__ is getattr(original_class,method_name).__code__ and method_name not in vars(science))
    tree=ast.parse(textwrap.dedent(inspect.getsource(getattr(original_class,method_name))))
    calls=[n for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id==constructor_name]
    need(len(calls)==1 and callable(method.__func__.__globals__.get(constructor_name)))
    old_constructor=method.__func__.__globals__[constructor_name]
    need(old_constructor is getattr(N,constructor_name))
    selected_writer,writer_proof=EW.compile_writer(DW,whitelist=whitelist,control_module=control_module,mattermost_module=mattermost_module,scope_guard=scope_guard)
    unused_factory,bind_checkpoint,checkpoint_proof=EW.compile_checkpoint(DC,selected_writer=selected_writer,whitelist=whitelist)
    record=dict(owner=owner,science=science,whitelist=whitelist,phase='PARTIAL_RETAINED_NO_RETRY',
                original_constructor=old_constructor,selected_writer=selected_writer,
                bind_checkpoint=bind_checkpoint,checkpoints={})
    RETAINED[id(owner)]=record
    def constructor(*args,**kwargs):
        need(record['owner']is owner and record['science']is owner.scientific_smoke and
             record['phase']=='BOUND_ORIGINAL_PREPARATION_CONSUMER'and args and args[0]is core and
             scope_guard(core)is True and not core.scientific_activation_qualified and
             set(core.gate.startup_held)==set(core.rows))
        # No synthetic __new__, return proxy or bypass of the original guards.
        port=old_constructor(*args,**kwargs)
        need(type(port)is DynamicCheckpointPorts and port.core is core and port.t not in record['checkpoints'])
        record['checkpoints'][port.t]=dict(port=port,phase='CONSTRUCTED_PARTIAL_RETAINED_NO_RETRY')
        result=bind_checkpoint(port)
        need(result is port and type(result)is DynamicCheckpointPorts)
        record['checkpoints'][port.t]['phase']='BOUND_ORIGINAL_CHECKPOINT_INSTANCE'
        return port
    original=method.__func__
    selected=FunctionType(original.__code__,dict(original.__globals__,**{constructor_name:constructor}),
        original.__name__,original.__defaults__,original.__closure__)
    selected.__kwdefaults__=original.__kwdefaults__
    selected,orderproof=prerelease_order.select(selected,canonical=getattr(original_class,method_name),mode=order_mode)
    setattr(science,method_name,MethodType(selected,science))
    need(prerelease_order.matches(getattr(science,method_name).__func__,canonical=getattr(original_class,method_name),mode=order_mode) and
         core.ledger.db.total_changes==changes)
    record.update(phase='BOUND_ORIGINAL_PREPARATION_CONSUMER',constructor=constructor,prerelease_order_module=prerelease_order,order_proof=orderproof,selected_prepare=selected,canonical_prepare=getattr(original_class,method_name),tester_source_exported=False)
    return dict(schema='count14-newroot-msg210-original-science-checkpoint-consumer-bound-v1',
        approved_plan_sha256=PLAN,original_preparation_method=method_name,
        original_preparation_CodeType_unchanged=False,original_preparation_order_inverse_AST=True,
        prerelease_container_order=orderproof,constructor_call_sites=1,
        original_checkpoint_constructor_called_first_and_exact_object_retained=True,
        original_checkpoint_and_physical_types_and_preflight_begincut_CodeTypes_preserved=True,
        writer_selection=writer_proof,checkpoint_selection=checkpoint_proof,
        all_original_backup_roots_mount_indices_and_regular_bytes_preserved=True,
        no_new_owner_or_supervisor_or_container_actions=True,financial_writes_or_models=0,
        actual_checkpoint_construction_or_fresh_kernel_NOT_claimed=True)


def tester_prepare_source(owner):
    """Export only this same new cohort's registered writer/preflight AST once.

    Original bind_science's canonical MethodType/CodeType/no-instance-override
    guard has ALREADY run unchanged before idle/Tester installers. This is not a
    second binding or acceptance of any arbitrary previously modified method.
    """
    from native_formal_cohort import NativeFormalCohort
    record=RETAINED.get(id(owner));science=getattr(owner,'scientific_smoke',None)
    need(record is not None and record['owner']is owner and record['science']is science and
         type(science)is NativeFormalCohort and science.owner is owner and
         record['phase']=='BOUND_ORIGINAL_PREPARATION_CONSUMER'and
         record['tester_source_exported']is False and owner.core.contract['mode']=='production'and
         not owner.errors and not owner.core.scientific_activation_qualified and
         set(owner.core.gate.startup_held)==set(owner.core.rows)and
         all(row['checkpoint']is None and row['tester']is None and row['host']is None
             for row in science.tracks.values()))
    method=science._prepare_one
    need(type(method)is MethodType and method.__self__ is science and
         method.__func__ is record['selected_prepare']and
         method.__func__.__globals__['create_formal_checkpoint_ports']is record['constructor']and
         record['canonical_prepare']is NativeFormalCohort._prepare_one and
         sha(__import__('native_formal_cohort').__file__)==FORMAL_COHORT)
    tree,orderproof=record['prerelease_order_module'].selected_tree(method.__func__,
        canonical=record['canonical_prepare'],mode='formal')
    record['tester_source_exported']=True
    return method.__func__,tree,dict(original_writer_binding_guard_ran_before_first_method_override=True,
        same_exact_registered_selected_function_and_checkpoint_constructor=True,
        original_prerelease_order=orderproof,one_cold_typed_Tester_composition_only=True)
