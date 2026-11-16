"""One SAME-core concrete ORIGINAL FINAL controller; no extra owner/dispatch loop.

Private config reuses the original FINAL field dictionary per enabled trajectory.
Native code/evaluator assets/credentials stay opaque; the original full profile
is compiled and pinned before any experiment request can be released. Factory
retains every partial object/child and never retries or auto-releases models.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from types import MethodType, SimpleNamespace

from common import need, digest, hash_file, private_dir, publish, strict, wire
from original_relay_core import OriginalRelayCore
from model_capacity import ModelCapacity
from final_host_rpc import HostServer
from native_final_profile import compile_profile
from native_images import NativeImages, ORIGINAL_INVENTORY
from run_native_scientific6 import ScientificSixDriver, private_input
from smoke_checkpoint_final_runtime import SmokeFinalRuntimeScope, docker_scope_body, infrastructure_pins, load_profile_registry, exact_profile_transition_metadata, validate_exact_native_derived_sidecar

FINAL_FIELDS = {'native_directory', 'evaluator_root', 'image_mapping', 'image_mapping_sha256',
    'dependency_freeze_sha256', 'framework_root', 'docker_config', 'python_command',
    'environment', 'credential_source'}


# These are infrastructure ports only. Every other original domain file and
# every native/evaluator/source/model/image/policy asset must remain byte-equal.
PROFILE_INFRASTRUCTURE_FILES = frozenset((
    'native_final_runtime.py', 'native_final_profile.py', 'native_images.py',
    'native_final_dispatch.py', 'run_native_final_child.py', 'run_native_scientific6.py'))


def derive_profile_registration(contract, actual, reference):
    historical = contract['v2_baseline_reference_protocol']['final_v21']
    actual_sha = digest(actual)
    if actual_sha == historical:
        return {'original_profile_sha256': actual_sha, 'protocol_sha256': historical,
                'scope_profile': None}
    need(reference is not None and digest(reference) == historical,
         'SMOKE_FINAL_UNQUALIFIED_NEEDS_EXACT_PUBLIC_REFERENCE_PROFILE_METADATA')
    transition=exact_profile_transition_metadata(actual,reference,historical=historical)
    changes=transition['domain_diff'];native_compatibility=transition['native_import_enum_compatibility']
    sidecar = {'schema': ('count14-smoke-final-derived-infrastructure-profile-v1' if native_compatibility is None else 'count14-smoke-final-derived-exact-native-infrastructure-profile-v2'),
        'contract_sha256': digest(contract), 'historical_v2_reference_sha256': historical,
        'original_profile_sha256': actual_sha, 'protocol': 'v2.1',
        'scientific_assets_exact_reference_match': native_compatibility is None,
        'scientific_non_code_profile_fields_exact_reference_match': True,
        'equal_profile_fields': transition['equal_profile_fields'],
        'unchanged_domain_file_sha256': transition['unchanged_domain_file_sha256'],
        'infrastructure_domain_diff': changes, 'infrastructure_source_sha256': infrastructure_pins(),
        'eval_docker_socket': contract['finalization']['eval_docker_socket'],
        'settings': ['DYNTEAM', 'DYNTEAM_RACING'], 'checkpoint_tokens': [500000, 1000000],
        'exact_labels': ['s500000t', 's1000000t'],
        'accounting_rng_schema_model_transport_evaluator_formulas_changed': False}
    if native_compatibility is not None:
        sidecar['native_import_enum_compatibility']=copy.deepcopy(native_compatibility)
        sidecar['actual_profile_metadata']=copy.deepcopy(actual)
        sidecar['reference_profile_metadata']=copy.deepcopy(reference)
        validate_exact_native_derived_sidecar(sidecar,historical=historical,actual_sha256=actual_sha)
    if 'native_model_port.py' in changes:
        sidecar['provider_response_field_compatibility'] = {
            'schema': 'count14-msg228-reasoning-alias-exact-domain-pair-v1',
            'aliases': ['reasoning_content', 'reasoning'],
            'domain_change': changes['native_model_port.py'],
            'raw_SSE_request_format_usage_finish_UNKNOWN_unchanged': True}
    return {'original_profile_sha256': actual_sha, 'protocol_sha256': digest(sidecar),
            'scope_profile': sidecar}


def core_home(core):
    path=Path(core.home)
    need(path.is_absolute()and path.resolve()==path and path.is_dir(),'SMOKE_FINAL_SAME_CORE_INFRA_DIAGNOSTIC_HOME')
    return path

def publish_import_pins(destination):
    """Current loaded OWN/original framework roots only; no cwd/site discovery."""
    import smoke_checkpoint_final_scope
    import native_final_runtime
    import glm_session_header
    roots = []
    for module in (smoke_checkpoint_final_scope, native_final_runtime, glm_session_header):
        root = Path(module.__file__).resolve().parent
        need(root.is_absolute() and root.resolve() == root and root.is_dir(),
             'SMOKE_FINAL_PINNED_FRAMEWORK_SOURCE_ROOT')
        if root not in roots:roots.append(root)
    value = {'schema': 'count14-smoke-final-frozen-imports-v1',
             'roots': [{'path': str(root), 'files': {p.name: hash_file(p)['sha256']
                        for p in sorted(root.glob('*.py'))}} for root in roots]}
    destination = Path(destination)
    publish(destination, wire(value), mode=0o400)
    return destination, hash_file(destination)['sha256']


class SmokeFinalController:
    def preflight(self):
        need(self.state == 'CREATED_REQUIRES_PREFLIGHT',
             'SMOKE_FINAL_PREFLIGHT_ONCE_RETAIN_PARTIAL_NO_RETRY')
        self.state = 'PREPARING_ORIGINAL_FINAL'
        try:self._prepare(self.config_path, self.config_sha256)
        except BaseException as error:
            frames = []; tb = error.__traceback__
            while tb:
                frames.append({'file': tb.tb_frame.f_code.co_filename, 'line': tb.tb_lineno,
                               'function': tb.tb_frame.f_code.co_name}); tb = tb.tb_next
            self.errors.append({'PUBLIC_code': 'SMOKE_FINAL_PARTIAL_RETAINED_NO_RETRY',
                                'exception_type': type(error).__name__, 'locations': frames,
                                'refusal_code': getattr(error, 'code', None),
                                'exception_message': str(error), 'infra_traceback': traceback.format_exc()})
            # Persist the original inner error outside all scientific locks and
            # without dumping config, locals, environment or model/task bodies.
            try:
                diagnostic=private_dir(core_home(self.core)/'final-preflight-infra-diagnostics',create=True)
                target=diagnostic/'FAILED_RETAINED_PUBLIC.json'
                raw=wire(self.errors[-1]);publish(target,raw,mode=0o400)
                self.errors[-1]['diagnostic_reference']={'path':str(target),'sha256':__import__('hashlib').sha256(raw).hexdigest()}
            except BaseException as persistence_error:
                self.errors.append({'PUBLIC_code':'SMOKE_FINAL_INFRA_DIAGNOSTIC_PERSIST_FAILED_RETAIN_ORIGINAL',
                                    'exception_type':type(persistence_error).__name__})
            self.state = 'PARTIAL_RETAINED_MODELS_NOT_RELEASED'
        need(not self.errors and self.state == 'PREPARED_ORIGINAL_FINAL_MODELS_PAUSED',
             'SMOKE_FINAL_ACTUAL_PREFLIGHT_FAILED_RETAIN_ALL_ORIGINAL_OBJECTS')
        return self.public()

    def _prepare(self, config_path, config_sha256):
        core = self.core
        self.scope = SmokeFinalRuntimeScope(core.contract, contract_sha256=digest(core.contract))
        need(core.contract['mode'] == 'smoke' and set(core.gate.startup_held) == set(core.rows),
             'SMOKE_FINAL_PREPARE_ALL_SEARCH_STARTUP_HELD')
        with core.ledger.mutex:
            need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0 and
                 core.ledger.db.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0] == 0,
                 'SMOKE_FINAL_STATIC_PROFILE_BEFORE_FIRST_EXPERIMENT_MODEL')
        c = strict(private_input(config_path, config_sha256).read_bytes())
        need(type(c) is dict and set(c) in ({'schema', 'contract_sha256', 'trajectories'},
             {'schema', 'contract_sha256', 'trajectories', 'reference_profile'}) and
             c['schema'] == 'count14-dynteam-smoke-final-controller-v1' and
             c['contract_sha256'] == self.scope.sha and type(c['trajectories']) is dict,
             'SMOKE_FINAL_EXACT_PRIVATE_CONTROLLER_BINDING')
        enabled = set(c['trajectories'])
        baseline = {t for t, row in core.rows.items() if row['arm'] == 'DYNTEAM'}
        need(baseline <= enabled <= set(core.rows) and enabled,
             'SMOKE_FINAL_BASELINE_FIRST_OR_BOTH_EXACT_TRAJECTORIES')
        need(hasattr(core, 'system_health') and core.system_health.core is core,
             'SMOKE_FINAL_SAME_CORE_ORIGINAL_NEW_KEY_BINDING')
        key = Path(core.system_health.key_path)
        model_policy = copy.deepcopy(core.profile.policy)
        need(digest(model_policy) == core.profile.sha ==
             core.contract['v2_baseline_reference_protocol']['model_configuration'],
             'SMOKE_FINAL_SAME_ORIGINAL_SEARCH_MODEL_POLICY')
        reference = None
        if 'reference_profile' in c:
            item = c['reference_profile']
            need(type(item) is dict and set(item) == {'path', 'sha256'},
                 'SMOKE_FINAL_EXACT_PUBLIC_REFERENCE_PROFILE_DESCRIPTOR')
            reference = load_profile_registry(item['path'], item['sha256'])
            need(digest(reference) == core.contract['v2_baseline_reference_protocol']['final_v21'],
                 'SMOKE_FINAL_REFERENCE_METADATA_MUST_MATCH_HISTORICAL_PIN')
        self.config_sha256 = config_sha256
        registrations = {}
        self.final, self.profiles, self.facades = {}, {}, {}
        transports, classifiers, commands, environments = set(), set(), set(), []
        for t, original in c['trajectories'].items():
            need(type(original) is dict and set(original) == FINAL_FIELDS,
                 'SMOKE_FINAL_ORIGINAL_CONFIGURATION_FIELDS')
            f = copy.deepcopy(original); root = Path(core.rows[t]['root'])
            for name in ('native_directory', 'framework_root', 'docker_config', 'evaluator_root'):
                p = Path(f[name])
                need(p.is_absolute() and p.resolve() == p and p.is_relative_to(root) and p.is_dir(),
                     'SMOKE_FINAL_NEW_TRAJECTORY_NATIVE_ASSET_ROOT')
            need(Path(f['credential_source']) == key and key.is_absolute() and key.resolve() == key,
                 'SMOKE_FINAL_EXACT_SAME_NEW_PROVIDER_KEY_SOURCE')
            mapping = strict(Path(f['image_mapping']).read_bytes())
            need(type(mapping) is list and digest(mapping) == f['image_mapping_sha256'],
                 'SMOKE_FINAL_EXACT_ORIGINAL_IMAGE_MAPPING_METADATA')
            profile = compile_profile(f['native_directory'],
                source_bundle_sha256=core.contract['v2_baseline_reference_protocol']['source_bundle'],
                model_policy_sha256=digest(model_policy), evaluator_root=f['evaluator_root'],
                image_mapping_sha256=f['image_mapping_sha256'],
                dependency_freeze_sha256=f['dependency_freeze_sha256'])
            registrations[t] = derive_profile_registration(core.contract, profile, reference)
            self.scope.images(f['native_directory'], {'schema': 'count14-agensh-images-v1',
                'manifest_sha256': self.scope.sha, 'docker_host': core.contract['finalization']['eval_docker_socket'],
                'original_inventory_sha256': ORIGINAL_INVENTORY, 'images': mapping},
                manifest_sha256=self.scope.sha)
            transports.add(hash_file(Path(f['native_directory'])/'cc_streaming.py')['sha256'])
            classifiers.add(hash_file(Path(f['native_directory'])/'request_policy.py')['sha256'])
            command = tuple(f['python_command'])
            need(len(command) == 3 and set(command[1:]) == {'-I', '-B'} and
                 Path(command[0]).is_absolute() and Path(command[0]).is_file() and
                 type(f['environment']) is dict and all(type(k) is str and type(v) is str
                                                       for k, v in f['environment'].items()),
                 'SMOKE_FINAL_REAL_ISOLATED_PYTHON_COMMAND_AND_ENVIRONMENT')
            commands.add(command); environments.append(f['environment'])
            self.final[t], self.profiles[t] = f, profile
            home = private_dir(root/'final', create=True)
            need(not any(home.iterdir()), 'SMOKE_FINAL_NEW_POINT_CONFIGURATION_HOME')
            # Configuration-only state, not an experiment/scientific owner.
            facade = SimpleNamespace(root=home, points={}, manifest=core.contract,
                final=f, profile=profile, config={'model_policy': model_policy})
            facade.final_configuration = MethodType(docker_scope_body(ScientificSixDriver.final_configuration,
                core.contract['finalization']['eval_docker_socket'], expected_sites=2), facade)
            self.facades[t] = facade
        need(len(transports) == len(classifiers) == len(commands) == 1 and
             all(v == environments[0] for v in environments),
             'SMOKE_FINAL_ONE_ORIGINAL_TRANSPORT_CLASSIFIER_AND_CHILD_ENVIRONMENT')
        self.home = private_dir(core.home/'final-controller', create=True)
        need(not any(self.home.iterdir()), 'SMOKE_FINAL_NEW_CONCRETE_CONTROLLER_HOME')
        registry = {'schema': 'count14-smoke-final-scope-profile-registry-v1',
                    'contract_sha256': digest(core.contract), 'trajectories': registrations}
        registry_path = self.home/'FINAL_SCOPE_PROFILES_PUBLIC.json'
        publish(registry_path, wire(registry), mode=0o400)
        self.scope = SmokeFinalRuntimeScope(core.contract, contract_sha256=digest(core.contract), profile_registry=registry)
        core.smoke_final_scope_profiles = copy.deepcopy(registry)
        import_path, import_pin = publish_import_pins(self.home/'FINAL_IMPORTS_PUBLIC.json')
        env = dict(environments[0], COUNT14_SMOKE_FINAL_IMPORTS_PUBLIC=str(import_path),
                   COUNT14_SMOKE_FINAL_IMPORTS_SHA256=import_pin,
                   COUNT14_SMOKE_FINAL_PROFILE_PUBLIC=str(registry_path),
                   COUNT14_SMOKE_FINAL_PROFILE_SHA256=hash_file(registry_path)['sha256'])
        command = next(iter(commands)); entry = Path(__file__).with_name('smoke_checkpoint_final_child.py')
        # Real -I subprocess import proof, not compile/runpy. Retain Popen on any
        # timeout/failure and never kill, retry or substitute a successful marker.
        self.import_stdout = self.home/'ZERO_MODEL_IMPORT_PUBLIC.stdout'
        self.import_stderr = self.home/'ZERO_MODEL_IMPORT.stderr'
        with self.import_stdout.open('xb') as out, self.import_stderr.open('xb') as err:
            self.import_child = subprocess.Popen([*command, str(entry), '--verify-imports'],
                cwd=self.home, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, close_fds=True)
        rc = self.import_child.wait(timeout=30)
        need(rc == 0, 'SMOKE_FINAL_REAL_ISOLATED_IMPORT_CHILD_FAILED')
        observed = strict(self.import_stdout.read_bytes())
        need(observed == {'schema': 'count14-smoke-final-zero-model-import-v1', 'PASS': True,
             'isolated': True, 'external_models': 0, 'import_manifest_sha256': import_pin,
             'original_child_imported': True, 'original_runtime_imported': True},
             'SMOKE_FINAL_REAL_ISOLATED_IMPORT_PUBLIC_RECEIPT')
        self.capacity = self.scope.bind_capacity(ModelCapacity(core.ledger,
            native_transport_sha256=next(iter(transports)), native_classifier_sha256=next(iter(classifiers)),
            global_allocated_cap=96, auxiliary_cap=16))
        self.server = HostServer(self.home/'final-host.sock', self.capacity)
        self.server.start()
        if not hasattr(core.queue, '_smoke_scope_sha256'):self.scope.bind_queue(core.queue)
        need(core.queue._smoke_scope_sha256 == self.scope.sha,
             'SMOKE_FINAL_SAME_CORE_ORIGINAL_QUEUE_SCOPE')
        self.dispatcher = self.scope.dispatcher(core.ledger, core.queue, self.capacity, self.server,
            directory=self.home/'children', configuration=self.configuration,
            python_command=command, environment=env)
        self.state = 'PREPARED_ORIGINAL_FINAL_MODELS_PAUSED'
        publish(self.home/'FINAL_STATIC_PROFILE_PUBLIC.json', wire({
            'schema': 'count14-smoke-final-static-profile-v1', 'contract_sha256': self.scope.sha,
            'configuration_sha256': config_sha256, 'profiles': {t: digest(p) for t, p in self.profiles.items()},
            'original_reference_profile_match': {t: entry['scope_profile'] is None for t, entry in registrations.items()},
            'actual_scope_protocol_sha256': {t: entry['protocol_sha256'] for t, entry in registrations.items()},
            'scope_profile_registry_sha256': hash_file(registry_path)['sha256'], 'isolated_import_exit': rc,
            'experiment_models_started': 0, 'automatic_model_release': False}), mode=0o400)

    def configuration(self, job):
        need(self.state in ('PREPARED_ORIGINAL_FINAL_MODELS_PAUSED', 'RELEASED') and
             job['trajectory'] in self.facades, 'SMOKE_FINAL_ONLY_PREPARED_TRAJECTORY_CONFIGURATION')
        t = job['trajectory']
        self.scope.verify_input(job['input_root'], expected_policy_sha=job['input_policy'],
                                trajectory=t, setting=job['setting'])
        return self.facades[t].final_configuration(job)

    def release(self, *, owner_evidence):
        need(self.state == 'PREPARED_ORIGINAL_FINAL_MODELS_PAUSED',
             'SMOKE_FINAL_EXPLICIT_FRESH_OWNER_RELEASE_ONCE')
        self.capacity.release(owner_evidence=owner_evidence)
        self.state = 'RELEASED'

    def dispatch_one(self):
        need(self.state == 'RELEASED', 'SMOKE_FINAL_EXPLICIT_OWNER_RELEASE_REQUIRED')
        return self.dispatcher.dispatch_one()

    def poll(self):
        need(self.state in ('PREPARED_ORIGINAL_FINAL_MODELS_PAUSED', 'RELEASED'),
             'SMOKE_FINAL_PARTIAL_RETAINS_NO_RETRY')
        try:
            self.dispatcher.poll()
            if self.state == 'RELEASED':self.dispatcher.dispatch_one()
        finally:
            self.dispatcher.publish_first_failure_public()
        return self.public()

    def close_after_drained(self):
        need(self.state == 'RELEASED' and self.core.ledger.global_unresolved() == 0,
             'SMOKE_FINAL_CLOSE_REQUIRES_REAL_GLOBAL_PHYSICAL_TERMINAL')
        counts = self.core.queue.frontier()
        need(counts and set(counts) == {'COMPLETE'} and
             all(record['child'] is not None and record['terminal'] is not None and
                 record['child'].returncode is not None
                 for record in self.dispatcher.children.values()),
             'SMOKE_FINAL_ALL_ORIGINAL_K3_CHILDREN_AND_QUEUE_COMPLETE')
        self.server.close()
        self.state = 'CLOSED_FINAL_TERMINAL'
        return self.public()

    def public(self):
        return {'state': self.state, 'enabled_trajectory_count': len(getattr(self, 'profiles', {})),
                'original_shared_capacity_bound': self.capacity is not None,
                'original_final_host_bound': self.server is not None,
                'original_final_queue_counts': self.core.queue.frontier(),
                'original_final_children_retained': 0 if self.dispatcher is None else len(self.dispatcher.children),
                'original_final_points_audited': 0 if self.dispatcher is None else sum(
                    p['audited'] for p in self.dispatcher.points.values()),
                'error_types': [row['exception_type'] for row in self.errors]}

    def status(self):
        return {'state': self.state, 'errors': list(self.errors),
            'original_capacity_retained': self.capacity is not None,
            'original_host_server_retained': self.server is not None,
            'dispatcher': None if self.dispatcher is None else self.dispatcher.status(),
            'import_child_retained': self.import_child is not None}


def create_smoke_final_controller(core, config_path, config_sha256):
    need(type(core) is OriginalRelayCore and not hasattr(core, 'smoke_final_controller'),
         'SMOKE_FINAL_ONE_SAME_ORIGINAL_CORE_CONTROLLER')
    self = SmokeFinalController.__new__(SmokeFinalController)
    self.core = core; self.state = 'CREATED_REQUIRES_PREFLIGHT'; self.errors = []
    self.config_path, self.config_sha256 = config_path, config_sha256
    self.capacity = self.server = self.dispatcher = self.import_child = None
    core.smoke_final_controller = self  # retain before any fallible action
    return self
