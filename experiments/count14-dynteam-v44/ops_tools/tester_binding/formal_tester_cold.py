"""Explicit six typed tester sources and TWO private original cohort seams.

Companion is deployment metadata outside CODE/FROZEN, avoiding a scope/map
hash cycle. Missing or Game/cross-track scopes cannot silently become ports.
"""
from pathlib import Path
from types import MethodType
import ast
import copy
import hashlib
import inspect
import textwrap

SCHEMA='count14-formal100m-tester-bindings-v1'
CATALOGUE='3ac1d9773892c87fcd858ecafcee996a1083097f3052454c191b830685b4aca7'
BINDING='formal100m-tester-public-binding-wip-v1/formal_tester_public_binding.py'
PROTOCOL='formal100m-tester-public-binding-wip-v1/PROGRAM_REGISTRATION_PROTOCOL.md'
RUNNER='formal100m-tester-public-binding-wip-v1/tester-native-runner/smoke_racing_tools_public_runner.cjs'


def need(ok,code):
    if not ok:raise ValueError(code)


def read_sources(*,path,pin,code_root,contract):
    from formal_public_factory import base_helper
    from formal_public_common import digest,CONTRACT_CANONICAL_SHA
    from formal_tester_public_binding import TesterPublicBindingSources
    from count14_public_racing_judge import PublicToolScope
    import tester_public_tool_scope_compile as compiler
    helper=base_helper();root=Path(code_root);path=Path(path)
    need(path.name=='TESTER_BINDINGS_PUBLIC.json' and not path.is_relative_to(root) and
         not any(part.startswith('OWN')for part in (*root.parts,*path.parts)),
         'FORMAL_TESTER_REAL_DEPLOYMENT_COMPANION_OUTSIDE_CODE_NOT_OWN')
    value=helper.public(path,pin)
    need(set(value)=={'schema','contract_sha256','frozen_execution_map_sha256','trajectories'} and
         value['schema']==SCHEMA and value['contract_sha256']==digest(contract)==CONTRACT_CANONICAL_SHA,
         'FORMAL_TESTER_EXACT_COMPANION_CONTRACT_SCHEMA')
    manifest_pin=value['frozen_execution_map_sha256'];helper._sha(manifest_pin)
    # This is the final installed CODE metadata, NOT the local draft map anchor.
    manifest=helper.public(root/'formal-tester-current-declaration-msg238-v3'/'CURRENT_EXECUTION_DECLARATION_PUBLIC.json',manifest_pin,8*1024*1024)
    rows=value['trajectories'];expected={r['trajectory_id']for r in contract['trajectories']}
    need(type(rows)is dict and set(rows)==expected,'FORMAL_TESTER_EXACT_ALL_SIX_REGISTERED_TRAJECTORIES')
    original=compiler.original(root)
    profile=original.public(root/'ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json',original.PROFILE_SHA256)
    for relative in (RUNNER,'runtime-v1/smoke_racing_tools_public_exec.py',
                     'runtime-v1/formal_count14_tester_public.py',BINDING,PROTOCOL):
        actual=root/relative;record=manifest['files'][relative]
        need(actual.resolve()==actual and not actual.is_symlink() and actual.is_file() and
             hashlib.sha256(actual.read_bytes()).hexdigest()==record['sha256'],
             'FORMAL_TESTER_ALL_FIVE_ACTUAL_CODE_SOURCES_MATCH_FINAL_FROZEN_MAP')
    sources={};fields={'runner_host_path','runner_sha256','protocol_host_path','protocol_sha256','scope'}
    for t,row in rows.items():
        need(type(row)is dict and set(row)==fields,'FORMAL_TESTER_EXACT_TYPED_SOURCE_FIELDS')
        for key,relative,pinkey in(('runner_host_path',RUNNER,'runner_sha256'),('protocol_host_path',PROTOCOL,'protocol_sha256')):
            actual=Path(row[key]);record=manifest['files'][relative]
            need(actual==root/relative and actual.resolve()==actual and not actual.is_symlink() and actual.is_file() and
                 row[pinkey]==record['sha256'] and hashlib.sha256(actual.read_bytes()).hexdigest()==row[pinkey],
                 'FORMAL_TESTER_CANONICAL_CODE_AND_FINAL_EXECUTION_PIN_NOT_CROSS_SCOPE')
        # Reuse the fixed PURE metadata compiler to bind exact t+contract+map,
        # not just format-check an opaque Game or other track's six fields.
        scope,_=compiler.compile_tester(original,contract=contract,profile=profile,manifest=manifest,
            manifest_sha256=manifest_pin,trajectory=t,binding_module=BINDING,protocol=PROTOCOL,runner=RUNNER)
        need(row['scope']==scope and scope['original_count14_catalogue_sha256']==CATALOGUE,
             'FORMAL_TESTER_EXACT_PER_TRACK_COMPILER_SCOPE_NOT_GAME_OR_OTHER_TRACK')
        sources[t]=TesterPublicBindingSources(Path(row['runner_host_path']),row['runner_sha256'],
            Path(row['protocol_host_path']),row['protocol_sha256'],PublicToolScope(**scope).checked())
    return sources,dict(path=str(path),sha256=pin,frozen_execution_map_sha256=manifest_pin)


def install(cohort,*,sources_by_trajectory):
    from native_formal_cohort import NativeFormalCohort
    from formal_tester_public_binding import TesterPublicBindingSources,install_tester_public_bindings
    need(type(cohort)is NativeFormalCohort and not cohort.activation_attempted and
         set(cohort.core.gate.startup_held)==set(cohort.tracks) and
         type(sources_by_trajectory)is dict and set(sources_by_trajectory)==set(cohort.tracks) and
         all(type(s)is TesterPublicBindingSources for s in sources_by_trajectory.values()) and
         not hasattr(cohort,'formal_tester_cold_sources'),
         'FORMAL_TESTER_COLD_SAME_COHORT_EXACT_SIX_TYPED_SOURCES')
    need(all(r['tester'] is None and r['host'] is None for r in cohort.tracks.values()),
         'FORMAL_TESTER_INSTALL_PLAN_BEFORE_ANY_TESTER_CONSTRUCTOR_OR_CYCLE0')
    qualified,proof=compile_prepare_one(sources_by_trajectory,cohort=cohort)
    cohort._prepare_one=MethodType(qualified,cohort)
    cohort.formal_tester_cold_sources=dict(sources_by_trajectory)
    cohort.formal_tester_cold_inverse_AST=proof
    return proof


def compile_prepare_one(sources_by_trajectory,*,cohort=None):
    from native_formal_cohort import NativeFormalCohort
    from formal_tester_public_binding import install_tester_public_bindings
    original=NativeFormalCohort._prepare_one
    selection_proof=None
    if cohort is None:
        prior=ast.parse(textwrap.dedent(inspect.getsource(original)))
    else:
        from newroot_native_metadata import checkpoint_prepare_source_for_tester
        original,prior,selection_proof=checkpoint_prepare_source_for_tester(cohort)
    tree=copy.deepcopy(prior);hits=[]
    prepare=ast.dump(ast.parse("row['tester'].prepare()",mode='eval').body,include_attributes=False)
    class AddBindings(ast.NodeTransformer):
        def visit_Expr(self,node):
            if ast.dump(node.value,include_attributes=False)==prepare:
                hits.append('before_original_tester_prepare')
                hook=ast.parse("_cold_install_tester(core,t,row['tester'],sources=_cold_tester_sources[t])").body[0]
                return [hook,node]
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if (len(node.targets)==1 and isinstance(node.targets[0],ast.Subscript) and
                ast.dump(node.targets[0],include_attributes=False)==ast.dump(ast.parse("row['host']=None").body[0].targets[0],include_attributes=False) and
                isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='FormalHostWriters'):
                hits.append('after_original_host_constructor')
                hook=ast.parse("row['tester'].public_program_bindings.bind_formal_host_writer(row['host'])").body[0]
                return [node,hook]
            return self.generic_visit(node)
    tree=AddBindings().visit(tree)
    need(sorted(hits)==['after_original_host_constructor','before_original_tester_prepare'],
         'FORMAL_TESTER_EXACT_TWO_ORIGINAL_COHORT_COLD_SITES')
    reverted=copy.deepcopy(tree);removed=[]
    snippets={ast.dump(ast.parse(x).body[0],include_attributes=False)for x in(
        "_cold_install_tester(core,t,row['tester'],sources=_cold_tester_sources[t])",
        "row['tester'].public_program_bindings.bind_formal_host_writer(row['host'])")}
    class RemoveOnlyBindings(ast.NodeTransformer):
        def visit_Expr(self,node):
            if ast.dump(node,include_attributes=False)in snippets:removed.append(node);return None
            return self.generic_visit(node)
    reverted=RemoveOnlyBindings().visit(reverted)
    need(len(removed)==2 and ast.dump(reverted,include_attributes=False)==ast.dump(prior,include_attributes=False),
         'FORMAL_TESTER_OTHER_ORIGINAL_COHORT_SCIENCE_AND_HOST_ACTIONS_AST_UNCHANGED')
    namespace=dict(original.__globals__,_cold_install_tester=install_tester_public_bindings,
        _cold_tester_sources=dict(sources_by_trajectory))
    exec(compile(ast.fix_missing_locations(tree),__file__+':two-private-cold-binding-sites','exec'),namespace)
    proof=dict(insertion_count=2,reverse_AST_equal=True,
        original_class_or_source_changed=False,original_tester_prepare_and_host_constructor_retained=True)
    if selection_proof is not None:proof['same_original_checkpoint_writer_prerelease_composition']=selection_proof
    return namespace['_prepare_one'],proof
