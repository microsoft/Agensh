"""Natural typed sidecar on an EXACT original FormalFinalRuntimeScope instance.

Regular functions remain delegates; no NATURAL_STOP is ever called s10m etc.
Original immutable CAS/collector/v2.1, K3 queue/capacity, binding and engine math
run normally. A cold constructor wrapper must compose this before first bind.
This WIP is not a production grant or evidence of any real snapshot or K3.
"""
from pathlib import Path
from types import MethodType
from common import need,digest,hash_file
from formal_runtime import FormalFinalRuntimeScope as OriginalFormalScope
from formal_scope import FORMAL_CUTS,SETTINGS
from formal_ast import globals_clone
from formal_natural_compile import counted_redirect
import formal_natural_abi as abi


def augment_scope(scope):
    need(type(scope)is OriginalFormalScope and not hasattr(scope,'formal_natural_sidecar'),
         'FORMAL_NATURAL_ONE_EXACT_CURRENT_FORMAL_SCOPE_INSTANCE')
    old={name:getattr(scope,name) for name in ('_roster','label','verify_input','bind_capacity',
        'audit_three','install_exact_label_abi','final_binding','runtime','dispatcher','bind_queue')}
    scope.formal_natural_sidecar={'policy_sha256':abi.POLICY_SHA,'engine_authorities':{}}
    def roster(own,setting,snapshot):
        meta=abi.natural(snapshot)
        if meta is None:return old['_roster'](setting,snapshot)
        row=own._row(snapshot['trajectory'],setting)
        need(snapshot['pins']['manifest']==own.sha and set(snapshot['roles'])==set(row['roles']) and
             snapshot['target_tokens']==snapshot['actual_search_tokens']==meta['actual_tokens'] and
             snapshot['shortfall']==0,'FORMAL_NATURAL_SNAPSHOT_EXACT_ACTUAL_NOT_REGULAR_ALIAS')
        return True
    scope._roster=MethodType(roster,scope)
    scope.label=MethodType(lambda own,target,natural_stop=None:
        old['label'](target) if natural_stop is None else abi.label(target,natural_stop),scope)
    for name in ('_build','_verify','_audit','_register','_snapshot_verify'):
        function=counted_redirect(getattr(scope,name))
        if name=='_build':function=globals_clone(function,_smoke_roster=scope._roster)
        if name=='_audit':function=globals_clone(function,_smoke_label=scope.label)
        setattr(scope,name,function)
    def verify(own,destination,*,expected_policy_sha,trajectory,setting):
        row=own._row(trajectory,setting)
        policy=own._verify(destination,expected_policy_sha=expected_policy_sha,trajectory=trajectory,setting=setting)
        meta=abi.natural(policy)
        if meta is None:
            need(policy['pins']['manifest']==own.sha and policy['target_tokens']in FORMAL_CUTS and
                 set(policy['worker_to_native_input_role'])==set(row['roles']) and
                 'point_kind'not in policy and 'natural_stop'not in policy,'FORMAL_NATURAL_REGULAR_VERIFY_UNCHANGED')
        else:
            need(policy['pins']['manifest']==own.sha and policy['point_kind']==abi.KIND and
                 policy['natural_stop']==meta and set(policy['worker_to_native_input_role'])==set(row['roles']),
                 'FORMAL_NATURAL_EXACT_INPUT_SCOPE')
        return policy
    scope.verify_input=MethodType(verify,scope)
    def queue(own,value):
        result=old['bind_queue'](value)
        result.enqueue=MethodType(counted_redirect(result.enqueue.__func__),result)
        return result
    scope.bind_queue=MethodType(queue,scope)
    def capacity(own,value):
        # Original binder installs same pause, marker and ledger math first.
        result=old['bind_capacity'](value);regular_register=result.register_scope
        def register(bound,binding,*,authorize):
            meta=abi.natural_binding(binding)
            if meta is None:return regular_register(binding,authorize=authorize)
            own._row(binding.get('trajectory'),binding.get('setting'))
            need(binding.get('manifest_sha256')==own.sha,'FORMAL_NATURAL_CAPACITY_CANONICAL_CONTRACT')
            return own._register(bound,binding,authorize=authorize)
        result.register_scope=MethodType(register,result)
        return result
    scope.bind_capacity=MethodType(capacity,scope)
    def audit(own,aux_root,runs,**values):
        meta=values.get('natural_stop')
        if meta is None:return old['audit_three'](aux_root,runs,**values)
        own._row(values['trajectory'],values['setting'])
        need(meta==abi.metadata(values['trajectory'],meta['generation'],values['target_tokens']),
             'FORMAL_NATURAL_TYPED_AUDIT_REAL_ACTUAL')
        return own._audit(aux_root,runs,**values)
    scope.audit_three=MethodType(audit,scope)
    # Keep every existing formal enum/RNG override. Relocate imports only in
    # the exact original binding functions while the original factory clones.
    from final_binding import FinalBinding
    original_clone=old['final_binding'].__func__.__globals__['_bind_globals']
    def clone(function,**bindings):
        if (function.__name__ in ('__init__','bind_request') and
            function.__code__.co_filename==FinalBinding.__init__.__code__.co_filename):
            # Preserve CURRENT qualified allowance body/host guard and only
            # relocate its original natural imports, never revert to class.
            function=counted_redirect(function)
        return original_clone(function,**bindings)
    scope.final_binding=MethodType(globals_clone(old['final_binding'].__func__,_bind_globals=clone),scope)
    old_runtime=old['runtime'].__func__
    install_body=old_runtime.__globals__['_install_body']
    def install_with_authority(own):
        original_install=counted_redirect(install_body(own))
        def install(runtime):
            original_install(runtime)
            meta=runtime.binding.natural_stop
            if meta is not None:
                own.formal_natural_sidecar['engine_authorities'][id(runtime.engine)]=(runtime.engine,meta)
        return install
    scope.runtime=MethodType(globals_clone(old_runtime,_install_body=install_with_authority),scope)
    def exact(own,engine,code,*,target):
        authority=own.formal_natural_sidecar['engine_authorities'].get(id(engine))
        if authority is None:return old['install_exact_label_abi'](engine,code,target=target)
        actual,meta=authority
        need(actual is engine and target==meta['actual_tokens'] and
             abi.label(target,meta)=='n'+str(target)+'t','FORMAL_NATURAL_ENGINE_ALREADY_INSTALLED_EXACT_AUTHORITY')
        # Original install() already executed the exact native label adapter.
        return None
    scope.install_exact_label_abi=MethodType(exact,scope)
    current_dispatcher=old['dispatcher']
    def dispatcher(own,*args,**kwargs):
        result=current_dispatcher(*args,**kwargs)
        # All existing failurepoll/fixed-producer constructors have completed
        # on THIS same d. Preserve their current code/globals/closures.
        original=result._poll.__func__
        result._poll=MethodType(counted_redirect(original),result)
        parent_entry=Path(result.entry).resolve()
        from formal_natural_final_child import PARENTS
        relative=str(parent_entry.relative_to(Path(__file__).resolve().parents[1]))
        need(relative in PARENTS and hash_file(parent_entry)['sha256']==PARENTS[relative],
             'FORMAL_NATURAL_EXACT_CURRENT_ALLOWANCE_CHILD_SOURCE')
        result.environment.update(COUNT14_NATURAL_PARENT_CHILD=str(parent_entry),
            COUNT14_NATURAL_PARENT_CHILD_SHA256=PARENTS[relative])
        result.entry=Path(__file__).with_name('formal_natural_final_child.py')
        result.entry_pin=hash_file(result.entry)
        return result
    scope.dispatcher=MethodType(dispatcher,scope)
    return scope


def FormalFinalRuntimeScope(*args,**kwargs):
    """Cold callable returning the EXACT original type, not a stand-in class."""
    return augment_scope(OriginalFormalScope(*args,**kwargs))


def compile_original_runtime_routes(scope):
    """Compile only, no runtime/dispatcher constructor or private body access."""
    from formal_runtime import _formal_install_body,_formal_poll_body
    from final_queue import FinalQueue
    return dict(install=counted_redirect(_formal_install_body(scope)),
                poll=counted_redirect(_formal_poll_body(scope)),
                enqueue=counted_redirect(FinalQueue.enqueue))
