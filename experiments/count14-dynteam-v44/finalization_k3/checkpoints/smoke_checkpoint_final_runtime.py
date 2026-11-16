"""Real ORIGINAL v2.1 child/runtime/dispatcher, exact paired smoke scope.

No model/evaluator/prompt/retry/metric function is replaced. Infrastructure
lookups bind the canonical contract SHA, actual arm, its own root and its exact
500k/1M label. The original complete FINAL profile still must verify unchanged.
"""
from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path
import textwrap
from types import MethodType, SimpleNamespace

from common import need, digest, hash_file
from final_binding import FinalBinding
from native_final_runtime import NativeFinalRuntime
from native_final_dispatch import NativeFinalDispatcher
from native_materialization import NativeMaterializer
from native_space import NativeSpace
from native_images import NativeImages
from smoke_checkpoint_final_scope import SmokeCheckpointFinalScope, CUTS, SETTINGS, _bind_globals, _scoped_body


def infrastructure_pins():
    import glm_session_header
    root = Path(__file__).resolve().parent
    names = ('smoke_checkpoint_final_scope.py', 'smoke_checkpoint_final_runtime.py',
             'smoke_checkpoint_final_child.py', 'smoke_checkpoint_final_controller.py')
    value = {name: hash_file(root/name)['sha256'] for name in names}
    value['glm_session_header.py'] = hash_file(Path(glm_session_header.__file__).resolve())['sha256']
    return value



PROFILE_INFRASTRUCTURE_DOMAIN_FILES = frozenset((
    'native_final_runtime.py','native_final_profile.py','native_images.py',
    'native_final_dispatch.py','run_native_final_child.py','run_native_scientific6.py'))
REASONING_DOMAIN_PAIR = {'reference_sha256':'2dc4f9995df5de57527bbea0598c17a8033e84b760b08251984da8d03aff3c7d','actual_sha256':'3c3ca87c19600fa05bb7a28821aeded23c6e64ecc366968adb242394ee5c555f'}
NATIVE_IMPORT_ENUM_PAIRS = {
    'level0_evaluator.py':{'reference_sha256':'1e468f089460c9de349912fb234ce394079fc5df73aee367fb0cedb5bd62a356','actual_sha256':'2d0e7ebc0befbe75f4a31115e91982828e1c0c4a1b51fc40bf6f08efd62e115e'},
    'limited_runner.py':{'reference_sha256':'5066234edd16abf58fec5a187d509297349d186ea1af83765a426062ec3c572a','actual_sha256':'0db848461778b7ae954fb5a3222723b33e89a51ec51915eee1bb7266216fb183'}}
NATIVE_IMPORT_ENUM_ADD = {'count14_official_runner.py':'2b6b0945728c76e0d4a49a8cf80e88d808f2593a1cf2fc11172e0f61be2fb8e6'}
NATIVE_ORIGIN_PAIR = {'reference_sha256':'f640e7f34a61c4eee90b6ae23e6c6c38e8a39c29306c0a22489d6632daa17636','actual_sha256':'c193188fd4d20de8ec0729b4a41bc4df7e15e38b54d84736147da0a546a147b6'}
NATIVE_IMPORT_ENUM_AST_EVIDENCE_SHA256 = '93b5de4c5b713cbb1134a7e6e06cc52249f510d65772c193a3e4ab1dae4a4a70'

EXACT_MSG236_RESPONSE_SANITY_DOMAIN_PAIRS = {'admission_gate.py': {'reference_sha256': '95319f965df921479c5fa737b70506ee3d904519288207ae4c108fd48d4ee1f7', 'actual_sha256': '8504daf99a91a322add5338b55677218f2cb3d103bee401eaae720c9048a3821'}, 'native_scientific_http.py': {'reference_sha256': '318b8eb75ee0293977090798baff0b7636a4514beb8c7bd73e36af145614f5e6', 'actual_sha256': 'eb08ff0d770f2609f24e568d4724e427dbde0b5327e7067d70759f0855e789d3'}, 'scientific_relay.py': {'reference_sha256': '49e70e88c3a736a4caeca00c13dde2c551f895f036ccd25de669fcbb681ff0a0', 'actual_sha256': '8b50d9de9106d5dd1314dec305189691cbcb7e7a2269fa6b54821f7c860d4c1e'}}

# User msg249/msg255 authorized context-only bounds and original driver consumer.
# These are exact immutable BEFORE/AFTER file pairs, not a generic allowlist.
EXACT_MSG255_API_CONTEXT_DOMAIN_PAIRS = {'protocol.py': {'reference_sha256': '9a4ce7add8ed3320b7b80f9cca3c8bb33286f7ae23a109f31282638dff46701f', 'actual_sha256': 'b52c8da3a6399b86b051ce157c574f5c1d06736014e1c746bff253b0e9c6adae'}, 'run_native_scientific6.py': {'reference_sha256': 'a85302b6a98c4c211a7799f13d281c6efb526528dc4ea6acdb0fbb109989d04e', 'actual_sha256': '8f805bdb5d5746f47916c9e9c05341058a43586634b2aa4e0f6b3599baeb7608'}}
# msg266 accepted FINAL custody/isolation infrastructure, exact BEFORE/AFTER only.
# No model, evaluator, fee, retry or scientific dictionary allowance is broadened.
EXACT_MSG266_FINAL_CONTROL_DOMAIN_PAIRS = {'final_queue.py': {'reference_sha256': '3b7b5041b7156a98e48ad6b5b65da483ddfd68113d6e52c9586983a219059881', 'actual_sha256': '7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c'}, 'native_final_dispatch.py': {'reference_sha256': 'fadb72e2ced6228133066390c51d60f5fa168b7e09b0c42ce44733beff27e45d', 'actual_sha256': 'ad316ddeaf332178f31598539ff66c6ff4d79280e2c5149f152719cd2d212201'}}
EXACT_REGISTERED_RESPONSE_DOMAIN_PAIRS = dict(EXACT_MSG236_RESPONSE_SANITY_DOMAIN_PAIRS, **EXACT_MSG255_API_CONTEXT_DOMAIN_PAIRS, **EXACT_MSG266_FINAL_CONTROL_DOMAIN_PAIRS)

def exact_profile_transition_metadata(actual,reference,*,historical):
    """PUBLIC metadata only; no native import/evaluator/task/body or actions.
    Changed maps are full dictionaries, never ignored aggregate strings.
    """
    need(type(actual)is type(reference)is dict and digest(reference)==historical and
         historical=='8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba'and set(actual)==set(reference),
         'SMOKE_FINAL_EXACT_HISTORICAL_METADATA_AND_FIELD_SET')
    maps=('domain_code_sha256','native_code_sha256','domain_asset_sha256')
    for key in maps:
        need(type(actual[key])is type(reference[key])is dict and
             all(type(n)is str and type(h)is str and len(h)==64 and all(c in '0123456789abcdef'for c in h)
                 for value in(actual[key],reference[key])for n,h in value.items()),
             'SMOKE_FINAL_COMPLETE_CODE_DICTIONARIES_NOT_AGGREGATE_ALLOWLIST')
    old,new=reference['domain_code_sha256'],actual['domain_code_sha256']
    need(set(old)==set(new),'SMOKE_FINAL_ORIGINAL_DOMAIN_FILE_SET_MUST_REMAIN_EXACT')
    domain_changes={n:{'reference_sha256':old[n],'actual_sha256':new[n]}for n in old if old[n]!=new[n]}
    allowed=PROFILE_INFRASTRUCTURE_DOMAIN_FILES
    if 'native_model_port.py'in domain_changes:
        need(domain_changes['native_model_port.py']==REASONING_DOMAIN_PAIR,'SMOKE_FINAL_MSG228_ONLY_EXACT_REASONING_ALIAS_DOMAIN_PAIR');allowed=allowed|{'native_model_port.py'}
    for name,pair in EXACT_REGISTERED_RESPONSE_DOMAIN_PAIRS.items():
        if name in domain_changes:
            need(domain_changes[name]==pair,'FORMAL_MSG236_EXACT_RECEIPT_EARLY_HOLD_INFRA_PAIR_ONLY')
            allowed=allowed|{name}
    need(domain_changes and set(domain_changes)<=allowed,'SMOKE_FINAL_ONLY_ENUMERATED_INFRASTRUCTURE_DOMAIN_DIFF_ALLOWED')
    native_changed=actual['native_code_sha256']!=reference['native_code_sha256']
    asset_changed=actual['domain_asset_sha256']!=reference['domain_asset_sha256']
    compatibility=None
    if native_changed or asset_changed:
        a,b=reference['native_code_sha256'],actual['native_code_sha256'];expected=dict(a)
        need(len(a)==557 and set(NATIVE_IMPORT_ENUM_ADD).isdisjoint(a),
             'SMOKE_FINAL_SOURCE6_EXACT_NATIVE_REFERENCE_557_NO_PRIOR_ADDED_ALIAS')
        for name,pair in NATIVE_IMPORT_ENUM_PAIRS.items():
            need(a.get(name)==pair['reference_sha256'],'SMOKE_FINAL_SOURCE6_EXACT_NATIVE_BEFORE_PAIR');expected[name]=pair['actual_sha256']
        expected.update(NATIVE_IMPORT_ENUM_ADD)
        need(b==expected and len(b)==558,'SMOKE_FINAL_SOURCE6_ONLY_TWO_IMPORTS_PLUS_EXACT_ORIGINAL_RUNNER_NO_REMOVE')
        a,b=reference['domain_asset_sha256'],actual['domain_asset_sha256'];expected=dict(a)
        need(len(a)==20 and a.get('NATIVE_FINAL_CODE_ORIGIN.json')==NATIVE_ORIGIN_PAIR['reference_sha256'],
             'SMOKE_FINAL_SOURCE6_EXACT_OLD_ORIGIN_DICTIONARY')
        expected['NATIVE_FINAL_CODE_ORIGIN.json']=NATIVE_ORIGIN_PAIR['actual_sha256']
        need(b==expected and len(b)==20,'SMOKE_FINAL_SOURCE6_ONLY_EXACT_ORIGIN_ASSET_PROVENANCE_CHANGE')
        need(len(old)==81 and domain_changes==dict(EXACT_REGISTERED_RESPONSE_DOMAIN_PAIRS,**{'native_model_port.py':REASONING_DOMAIN_PAIR}),
             'SMOKE_FINAL_SOURCE6_OTHER_80_DOMAIN_CODE_FILES_MUST_REMAIN_EXACT')
        compatibility=dict(schema='count14-source6-exact-native-import-official-enum-closure-v1',
            native_changed=NATIVE_IMPORT_ENUM_PAIRS,native_added=NATIVE_IMPORT_ENUM_ADD,native_removed={},
            origin_change=NATIVE_ORIGIN_PAIR,whole_method_selector_enum_AST_evidence_sha256=NATIVE_IMPORT_ENUM_AST_EVIDENCE_SHA256,
            unchanged_native_file_sha256={n:actual['native_code_sha256'][n]for n in reference['native_code_sha256']if n not in NATIVE_IMPORT_ENUM_PAIRS},
            unchanged_domain_asset_sha256={n:actual['domain_asset_sha256'][n]for n in reference['domain_asset_sha256']if n!='NATIVE_FINAL_CODE_ORIGIN.json'},
            unchanged_domain_file_sha256={n:new[n]for n in old if n not in domain_changes},
            exact_receipt_and_user_early_HOLD_infrastructure_pairs=EXACT_MSG236_RESPONSE_SANITY_DOMAIN_PAIRS,
            exact_user_msg255_api_context_domain_pairs=EXACT_MSG255_API_CONTEXT_DOMAIN_PAIRS,
            exact_user_msg266_final_control_domain_pairs=EXACT_MSG266_FINAL_CONTROL_DOMAIN_PAIRS)
        need(len(compatibility['unchanged_native_file_sha256'])==555 and len(compatibility['unchanged_domain_asset_sha256'])==19 and len(compatibility['unchanged_domain_file_sha256'])==73,
             'SMOKE_FINAL_SOURCE6_MSG266_ALL_555_19_73_UNCHANGED_DICTIONARY_ENTRIES_REQUIRED')
    excluded={'domain_code_sha256'}if compatibility is None else set(maps)
    need(all(actual[k]==reference[k]for k in actual if k not in excluded),
         'SMOKE_FINAL_SCIENTIFIC_INPUT_POLICY_IMAGES_ROSTER_DEPENDENCIES_CONTEXT_TURNS_AND_OTHER_FIELDS_EXACT')
    return dict(equal_profile_fields=sorted(k for k in actual if k not in excluded),domain_diff=domain_changes,
                unchanged_domain_file_sha256={n:new[n]for n in old if n not in domain_changes},native_import_enum_compatibility=compatibility)

def validate_exact_native_derived_sidecar(sidecar,*,historical,actual_sha256):
    need(type(sidecar)is dict and sidecar.get('schema')=='count14-smoke-final-derived-exact-native-infrastructure-profile-v2'and
         sidecar.get('historical_v2_reference_sha256')==historical and sidecar.get('original_profile_sha256')==actual_sha256,
         'SMOKE_FINAL_EXACT_NATIVE_SIDECAR_SCHEMA_AND_PIN')
    actual=sidecar['actual_profile_metadata'];reference=sidecar['reference_profile_metadata']
    need(digest(actual)==actual_sha256 and digest(reference)==historical,'SMOKE_FINAL_EXACT_NATIVE_SIDECAR_COMPLETE_ACTUAL_AND_REFERENCE_PROFILES')
    expected=exact_profile_transition_metadata(actual,reference,historical=historical)
    need(expected['native_import_enum_compatibility']is not None and
         sidecar['native_import_enum_compatibility']==expected['native_import_enum_compatibility']and
         sidecar['equal_profile_fields']==expected['equal_profile_fields']and
         sidecar['infrastructure_domain_diff']==expected['domain_diff']and
         sidecar['unchanged_domain_file_sha256']==expected['unchanged_domain_file_sha256']and
         sidecar['scientific_assets_exact_reference_match']is False and
         sidecar['scientific_non_code_profile_fields_exact_reference_match']is True and
         sidecar['accounting_rng_schema_model_transport_evaluator_formulas_changed']is False,
         'SMOKE_FINAL_EXACT_NATIVE_SIDECAR_CONSUMER_FULL_DICTIONARY_CLOSURE_NO_GENERIC_NATIVE_ALLOW')
    return True


def load_profile_registry(path, expected_sha256):
    import os, stat
    from common import strict
    p = Path(path)
    metadata = p.lstat()
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
         stat.S_ISREG(metadata.st_mode) and metadata.st_uid in (0, os.geteuid()) and
         not metadata.st_mode & 0o022 and metadata.st_nlink == 1 and metadata.st_size <= 4 * 1024 * 1024 and
         hash_file(p)['sha256'] == expected_sha256, 'SMOKE_EXACT_PUBLIC_FINAL_PROFILE_REGISTRY_PIN')
    return strict(p.read_bytes())


def docker_scope_body(function, docker_host, *, expected_sites):
    """Only historical default-daemon infrastructure strings become exact scope."""
    need(type(docker_host) is str and docker_host.startswith('unix:///') and
         Path(docker_host[7:]).is_absolute(), 'SMOKE_EXACT_CONTRACT_EVALUATOR_DOCKER_SOCKET')
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    count = 0
    class Endpoint(ast.NodeTransformer):
        def visit_Constant(self, node):
            nonlocal count
            if node.value == 'unix:///var/run/docker.sock':
                count += 1
                return ast.copy_location(ast.Constant(docker_host), node)
            return node
    tree = Endpoint().visit(tree)
    need(count == expected_sites, 'SMOKE_EXACT_ORIGINAL_EVALUATOR_DOCKER_ENDPOINT_SITES')
    namespace = {}
    exec(compile(ast.fix_missing_locations(tree), inspect.getsourcefile(function) + ':SYSTEM_SMOKE_EVAL_SOCKET', 'exec'),
         function.__globals__, namespace)
    return namespace[function.__name__]


def _install_body(scope):
    """Only original infrastructure setting/registered-cut lookups change."""
    original = NativeFinalRuntime.install
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    found = dict(spec=0, settings=0, cuts=0)

    class Infrastructure(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == 'spec':
                found['spec'] += 1
                node.body = ast.parse('return _smoke_setting_spec(self, setting)').body
                return node
            return self.generic_visit(node)

        def visit_Tuple(self, node):
            if [x.value for x in node.elts if isinstance(x, ast.Constant)] == ['Agensh-16', 'Agensh-1']:
                found['settings'] += 1
                return ast.copy_location(ast.Tuple(elts=[ast.Constant(x) for x in SETTINGS], ctx=ast.Load()), node)
            return self.generic_visit(node)

        def visit_List(self, node):
            if [x.value for x in node.elts if isinstance(x, ast.Constant)] == [10000000, 20000000]:
                found['cuts'] += 1
                return ast.copy_location(ast.List(elts=[ast.Constant(x) for x in CUTS], ctx=ast.Load()), node)
            return self.generic_visit(node)

    tree = Infrastructure().visit(tree)
    need(found == dict(spec=1, settings=1, cuts=1), 'SMOKE_EXACT_ORIGINAL_RUNTIME_INFRASTRUCTURE_SITES')
    def spec(runtime, setting):
        row = scope._row(runtime.binding.trajectory, setting)
        need(set(runtime.binding.policy['worker_to_native_input_role']) == set(row['roles']),
             'SMOKE_RUNTIME_ALL_ORIGINAL_FROZEN_INPUT_ROLES')
        return SimpleNamespace(final_mode='synthesize', proposals=len(row['roles']))
    namespace = {}
    space = dict(original.__globals__, _smoke_setting_spec=spec, digest=scope.canonical_runtime_digest)
    exec(compile(ast.fix_missing_locations(tree), inspect.getsourcefile(original) + ':SYSTEM_SMOKE_SCOPE', 'exec'), space, namespace)
    return namespace['install']


def _poll_body(scope):
    tree = ast.parse(textwrap.dedent(inspect.getsource(NativeFinalDispatcher._poll)))
    # Use the original source again for a single explicit verified rewrite pass.
    found = dict(verify=0, protocol=0, label=0)
    wanted = ast.dump(ast.parse("c['manifest']['protocol']", mode='eval').body, include_attributes=False)

    class Infrastructure(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if node.module == 'v21_inputs' and len(node.names) == 1 and node.names[0].name == 'verify_input':
                found['verify'] += 1
                return ast.Assign(targets=[ast.Name(id='verify_input', ctx=ast.Store())], value=ast.Name(id='_smoke_verify_input', ctx=ast.Load()))
            if node.module == 'r16_natural_contract':
                old = [x for x in node.names if x.name == 'label' and x.asname == 'point_label']
                if old:
                    need(len(old) == 1, 'SMOKE_POLL_ONE_ORIGINAL_LABEL_IMPORT')
                    found['label'] += 1
                    remaining = [x for x in node.names if x not in old]
                    result = [ast.ImportFrom(module=node.module, names=remaining, level=node.level)] if remaining else []
                    return result + [ast.Assign(targets=[ast.Name(id='point_label', ctx=ast.Store())], value=ast.Name(id='_smoke_label', ctx=ast.Load()))]
            return node

        def visit_Subscript(self, node):
            if ast.dump(node, include_attributes=False) == wanted:
                found['protocol'] += 1
                return ast.copy_location(ast.parse("_smoke_protocol(c['manifest'], j['trajectory'])", mode='eval').body, node)
            return self.generic_visit(node)

    tree = Infrastructure().visit(tree)
    need(found == dict(verify=1, protocol=2, label=1), 'SMOKE_EXACT_ORIGINAL_DISPATCH_AUDIT_SITES')
    def protocol(manifest, trajectory):
        need(manifest == scope.contract and digest(manifest) == scope.sha,
             'SMOKE_DISPATCH_CANONICAL_PROTOCOL_LOOKUP')
        return scope.protocol(trajectory)
    namespace = {}
    space = dict(NativeFinalDispatcher._poll.__globals__, _smoke_verify_input=scope.verify_input,
                 _smoke_label=scope.label, _smoke_protocol=protocol, audit_three=scope.audit_three)
    exec(compile(ast.fix_missing_locations(tree), inspect.getsourcefile(NativeFinalDispatcher._poll) + ':SYSTEM_SMOKE_SCOPE', 'exec'), space, namespace)
    return namespace['_poll']


class SmokeFinalRuntimeScope(SmokeCheckpointFinalScope):
    def __init__(self, contract, *, contract_sha256, profile_registry=None):
        super().__init__(contract, contract_sha256=contract_sha256)
        self.profile_registry = copy.deepcopy(profile_registry)
        self.profile_registry_sha256 = None if profile_registry is None else digest(profile_registry)
        if profile_registry is not None:
            need(type(profile_registry) is dict and set(profile_registry) == {'schema', 'contract_sha256', 'trajectories'} and
                 profile_registry['schema'] == 'count14-smoke-final-scope-profile-registry-v1' and
                 profile_registry['contract_sha256'] == self.sha and
                 set(profile_registry['trajectories']) <= set(self.rows), 'SMOKE_EXACT_REGISTERED_FINAL_PROFILE_SIDECAR')
            for t, entry in profile_registry['trajectories'].items():
                need(set(entry) == {'original_profile_sha256', 'protocol_sha256', 'scope_profile'} and
                     (entry['scope_profile'] is None and entry['protocol_sha256'] == entry['original_profile_sha256'] ==
                      self.contract['v2_baseline_reference_protocol']['final_v21'] or
                      entry['scope_profile'] is not None and digest(entry['scope_profile']) == entry['protocol_sha256'] and
                      entry['scope_profile']['contract_sha256'] == self.sha and
                      entry['scope_profile']['original_profile_sha256'] == entry['original_profile_sha256'] and
                      entry['scope_profile']['infrastructure_source_sha256'] == infrastructure_pins()),
                     'SMOKE_EXACT_ORIGINAL_OR_EXPLICIT_DERIVED_FINAL_PROFILE_PIN')
                if entry['scope_profile']is not None and entry['scope_profile'].get('schema')=='count14-smoke-final-derived-exact-native-infrastructure-profile-v2':
                    validate_exact_native_derived_sidecar(entry['scope_profile'],historical=self.contract['v2_baseline_reference_protocol']['final_v21'],actual_sha256=entry['original_profile_sha256'])

    def protocol(self, trajectory):
        need(trajectory in self.rows and (self.profile_registry is None or
             digest(self.profile_registry) == self.profile_registry_sha256), 'SMOKE_FINAL_PROFILE_REGISTRY_IMMUTABLE')
        value = copy.deepcopy(self.contract['v2_baseline_reference_protocol'])
        if self.profile_registry is not None:
            need(trajectory in self.profile_registry['trajectories'], 'SMOKE_FINAL_TRAJECTORY_PROFILE_NOT_PREPARED')
            value['final_v21'] = self.profile_registry['trajectories'][trajectory]['protocol_sha256']
        return value

    def protocol_sha256(self, trajectory):
        return self.protocol(trajectory)['final_v21']

    def projection(self, trajectory):
        need(trajectory in self.rows and digest(self.contract) == self.sha,
             'SMOKE_RUNTIME_EXACT_CANONICAL_CONTRACT')
        row = self.rows[trajectory]
        # Explicit infrastructure projection, never canonical hash of a wrapper.
        return {'root': row['root'], 'protocol': self.protocol(trajectory),
                'new_scope_contract': copy.deepcopy(self.contract), 'scope_trajectory': trajectory}

    def canonical_runtime_digest(self, value):
        if type(value) is dict and set(value) == {'root', 'protocol', 'new_scope_contract', 'scope_trajectory'}:
            t = value['scope_trajectory']
            need(t in self.rows and value == self.projection(t),
                 'SMOKE_RUNTIME_INFRASTRUCTURE_PROJECTION_CHANGED')
            return self.sha
        return digest(value)

    def images(self, native_directory, freeze, *, manifest_sha256, **kwargs):
        need(manifest_sha256 == self.sha and freeze['docker_host'] == self.contract['finalization']['eval_docker_socket'],
             'SMOKE_IMAGES_CANONICAL_CONTRACT_AND_EXACT_EVALUATOR_DAEMON')
        result = NativeImages.__new__(NativeImages)
        docker_scope_body(NativeImages.__init__, self.contract['finalization']['eval_docker_socket'],
                          expected_sites=1)(result, native_directory, freeze,
                                            manifest_sha256=manifest_sha256, **kwargs)
        return result

    def _binding(self, manifest, model_policy, model_policy_sha256, **kwargs):
        t = kwargs['trajectory']
        need(manifest == self.contract or manifest == self.projection(t),
             'SMOKE_RUNTIME_BINDING_CANONICAL_CONTRACT_OR_EXACT_PROJECTION')
        result = self.final_binding(model_policy, model_policy_sha256=model_policy_sha256, **kwargs)
        if self.profile_registry is not None:
            need(result.policy['pins']['protocol'] == self.protocol_sha256(t),
                 'SMOKE_FINAL_INPUT_EXACT_REGISTERED_SCOPE_PROTOCOL_PIN')
        return result

    def _materializer(self, *args, **kwargs):
        result = NativeMaterializer.__new__(NativeMaterializer)
        # Install before original ctor captures its bound scope in the exact
        # original materialization-function infrastructure namespace.
        result.scope = MethodType(_bind_globals(NativeMaterializer.scope, verify_input=self.verify_input), result)
        NativeMaterializer.__init__(result, *args, **kwargs)
        return result

    def runtime(self, *, manifest, trajectory, **kwargs):
        need(manifest == self.contract and digest(manifest) == self.sha,
             'SMOKE_CHILD_CANONICAL_MANIFEST_REQUIRED')
        row = self.rows[trajectory]
        root = Path(row['root'])
        # Root, input, code and AUX still undergo original physical/path checks.
        for name in ('input_root', 'aux_root', 'native_directory', 'space_home'):
            p = Path(kwargs[name])
            need(p.is_absolute() and p.is_relative_to(root), 'SMOKE_FINAL_EACH_ARM_OWN_ROOT')
        result = NativeFinalRuntime.__new__(NativeFinalRuntime)
        _bind_globals(NativeFinalRuntime.__init__, FinalBinding=self._binding,
            NativeMaterializer=self._materializer, digest=self.canonical_runtime_digest)(
            result, manifest=self.projection(trajectory), trajectory=trajectory, **kwargs)
        preflight = docker_scope_body(NativeFinalRuntime.preflight,
            self.contract['finalization']['eval_docker_socket'], expected_sites=1)
        from native_final_profile import verify_profile
        def verified_profile(profile, expected_sha256, code, **ports):
            if self.profile_registry is None:
                return verify_profile(profile, expected_sha256, code, **ports)
            entry = self.profile_registry['trajectories'][trajectory]
            need(expected_sha256 == self.protocol_sha256(trajectory),
                 'SMOKE_FINAL_RUNTIME_EXACT_REGISTERED_DERIVED_PROTOCOL')
            return verify_profile(profile, entry['original_profile_sha256'], code, **ports)
        result.preflight = MethodType(_bind_globals(preflight,
            digest=self.canonical_runtime_digest, verify_profile=verified_profile), result)
        result.space.scope = MethodType(_bind_globals(NativeSpace.scope,
            verify_input=self.verify_input), result.space)
        install = _install_body(self)
        scope = self
        def install_and_exact_label(runtime):
            install(runtime)
            # Exact qualified original fresh-key/X-SID metadata wrapper only.
            import importlib
            from glm_session_header import aux_transport
            stream = importlib.import_module('cc_streaming')
            stream.stream_call = aux_transport(stream.stream_call, runtime.port,
                key_path=runtime.root/'credentials'/'glm_api_key',
                receipt=runtime.root/f'GLM_AUX_SESSION_k{runtime.binding.repeat}_PUBLIC.json')
            scope.install_exact_label_abi(runtime.engine, runtime.code, target=runtime.binding.target)
        result.install = MethodType(install_and_exact_label, result)
        result.run = MethodType(_scoped_body(NativeFinalRuntime.run, label=self.label), result)
        return result

    def dispatcher(self, ledger, queue, capacity, server, *, directory, configuration,
                   python_command, environment):
        need(getattr(queue, '_smoke_scope_sha256', None) == self.sha and
             getattr(capacity, '_smoke_scope_sha256', None) == self.sha,
             'SMOKE_DISPATCH_BOUND_ORIGINAL_QUEUE_AND_CAPACITY')
        result = NativeFinalDispatcher(ledger, queue, capacity, server,
            directory=directory, configuration=configuration,
            python_command=python_command, environment=environment)
        result.entry = Path(__file__).with_name('smoke_checkpoint_final_child.py')
        result.entry_pin = hash_file(result.entry)
        result.dispatch_one = MethodType(_bind_globals(NativeFinalDispatcher.dispatch_one,
            FinalBinding=self._binding), result)
        result._poll = MethodType(_poll_body(self), result)
        return result
