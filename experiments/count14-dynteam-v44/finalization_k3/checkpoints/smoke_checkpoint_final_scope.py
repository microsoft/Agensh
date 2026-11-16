"""Exact SYSTEM_SMOKE scope ports around ORIGINAL checkpoint/K3 functions.

This adapts identity enumerations only, on explicitly bound instances. It never
supplies writer/cgroup/service evidence, an executor, transport or activation.
Original schemas, SQL, accounting, immutable records and K3 metrics are retained.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
from pathlib import Path
import textwrap
from types import FunctionType, MethodType

from common import need, digest, strict, sha, wire
from snapshot import CAS
from final_queue import FinalQueue
from model_capacity import ModelCapacity
import v21_inputs
import native_k3

SETTINGS = ('DYNTEAM', 'DYNTEAM_RACING')
CUTS = (500000, 1000000)


def _bind_globals(function, **bindings):
    result = FunctionType(function.__code__, dict(function.__globals__, **bindings),
                          function.__name__, function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def _scoped_body(function, *, settings=False, cuts=False, roster=None, label=None, snapshot_roster=None, sealed=None, participants=None):
    """Only exact original enum/roster/label sites may change; fail on drift."""
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    found = dict(settings=0, cuts=0, roster=0, label=0, snapshot_roster=0, sealed=0, participants=0)

    class Scope(ast.NodeTransformer):
        def visit_Tuple(self, node):
            value = [item.value for item in node.elts if isinstance(item, ast.Constant)]
            if settings and value == ['Agensh-16', 'Agensh-1']:
                found['settings'] += 1
                return ast.copy_location(ast.Tuple(elts=[ast.Constant(x) for x in SETTINGS], ctx=ast.Load()), node)
            if cuts and value == [10000000, 20000000]:
                found['cuts'] += 1
                return ast.copy_location(ast.Tuple(elts=[ast.Constant(x) for x in CUTS], ctx=ast.Load()), node)
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if participants is not None and any(isinstance(t, ast.Name) and t.id == 'expected' for t in node.targets):
                wanted = ast.parse("['worker:'+r for r in roles] + ['sdk:'+r+':'+p for r in roles for p in ('gitea','mattermost','board')]", mode='eval').body
                if ast.dump(node.value, include_attributes=False) == ast.dump(wanted, include_attributes=False):
                    found['participants'] += 1
                    node.value = ast.parse('_smoke_participants(cas, snapshot, proof)', mode='eval').body
            return self.generic_visit(node)

        def visit_Call(self, node):
            if snapshot_roster is not None and isinstance(node.func, ast.Name) and node.func.id == 'need' and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 'SNAPSHOT_ROLE_ROSTER':
                found['snapshot_roster'] += 1
                node.args[0] = ast.parse('_smoke_snapshot_roster(d)', mode='eval').body
            if roster is not None and isinstance(node.func, ast.Name) and node.func.id == 'need' and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 'FINAL_SETTING_ROSTER':
                found['roster'] += 1
                node.args[0] = ast.parse('_smoke_roster(setting, d)', mode='eval').body
            return self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if sealed is not None and node.module == 'native_writer_fence' and len(node.names) == 1 and node.names[0].name == 'verify_sealed_writer_proof':
                found['sealed'] += 1
                return ast.Assign(targets=[ast.Name(id='verify_sealed_writer_proof', ctx=ast.Store())], value=ast.Name(id='_smoke_sealed', ctx=ast.Load()))
            if label is not None and node.module == 'r16_natural_contract':
                old = [item for item in node.names if item.name == 'label' and item.asname == 'point_label']
                if old:
                    need(len(old) == 1, 'SMOKE_ONE_ORIGINAL_LABEL_IMPORT')
                    found['label'] += 1
                    remaining = [item for item in node.names if item not in old]
                    result = [ast.ImportFrom(module=node.module, names=remaining, level=node.level)] if remaining else []
                    result.append(ast.Assign(targets=[ast.Name(id='point_label', ctx=ast.Store())], value=ast.Name(id='_smoke_label', ctx=ast.Load())))
                    return result
            return node

    tree = Scope().visit(tree)
    for key, active in (('settings', settings), ('cuts', cuts), ('roster', roster is not None), ('label', label is not None), ('snapshot_roster', snapshot_roster is not None), ('sealed', sealed is not None), ('participants', participants is not None)):
        need(found[key] == (1 if active else 0), 'SMOKE_EXACT_ORIGINAL_' + key.upper() + '_SITE')
    space = dict(function.__globals__, _smoke_roster=roster, _smoke_label=label,
                 _smoke_snapshot_roster=snapshot_roster, _smoke_sealed=sealed,
                 _smoke_participants=participants)
    namespace = {}
    exec(compile(ast.fix_missing_locations(tree), inspect.getsourcefile(function) + ':SYSTEM_SMOKE_SCOPE', 'exec'), space, namespace)
    result = namespace[function.__name__]
    result._original_body_sha256 = hashlib.sha256(source.encode()).hexdigest()
    return result


class SmokeCheckpointFinalScope:
    def __init__(self, contract, *, contract_sha256):
        need(type(contract) is dict and digest(contract) == contract_sha256 and
             contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1' and
             contract.get('mode') == 'smoke', 'SMOKE_EXACT_FROZEN_PAIRED_CONTRACT')
        rows = contract['trajectories']
        need(len(rows) == 2 and {r['arm'] for r in rows} == set(SETTINGS) and
             len({r['trajectory_id'] for r in rows}) == 2 and
             all(r['checkpoints_tokens'] == list(CUTS) and r['search_tokens'] == CUTS[-1] and
                 r['request_cap'] == 13 and r['fees_domain'] == 'SYSTEM_SMOKE' and
                 r['roles'] and len(set(r['roles'])) == len(r['roles']) for r in rows),
             'SMOKE_EXACT_TWO_ARM_ROLE_AND_CUT_SCOPE')
        need(contract['capacities'] == {'AUX_total': 16, 'FINAL_jobs': 12, 'SEARCH_total': 78,
             'SYSTEM_probe_reserved': 2, 'all_own_relay_physical': 96, 'per_track_SEARCH': 13} and
             contract['finalization']['K'] == 3 and contract['finalization']['protocol'] == 'v2.1',
             'SMOKE_ORIGINAL_CAPACITY_AND_K3_CONTRACT')
        self.contract = copy.deepcopy(contract)
        self.sha = contract_sha256
        self.rows = {r['trajectory_id']: r for r in self.contract['trajectories']}
        self._build = _scoped_body(v21_inputs.build, cuts=True, roster=self._roster)
        self._verify = _scoped_body(v21_inputs.verify_input, cuts=True)
        self._audit = _scoped_body(native_k3.audit_three, settings=True, cuts=True, label=self.label)
        self._register = _scoped_body(ModelCapacity.register_scope, settings=True, cuts=True)
        self._pause = _scoped_body(ModelCapacity.pause, settings=True)
        from native_writer_fence import verify_sealed_writer_proof
        self._sealed = _scoped_body(verify_sealed_writer_proof, participants=self._sealed_participants)
        self._snapshot_verify = _scoped_body(CAS.verify_snapshot,
            snapshot_roster=self._snapshot_roster, sealed=self.verify_sealed_writer_proof)

    def _row(self, trajectory, setting):
        need(digest(self.contract) == self.sha and trajectory in self.rows,
             'SMOKE_FROZEN_TRAJECTORY')
        row = self.rows[trajectory]
        need(setting == row['arm'] and setting in SETTINGS, 'SMOKE_REAL_ARM_NOT_AGENSH_ALIAS')
        return row

    def _roster(self, setting, snapshot):
        row = self._row(snapshot['trajectory'], setting)
        need(set(snapshot['roles']) == set(row['roles']) and
             snapshot['target_tokens'] in CUTS and snapshot['pins']['manifest'] == self.sha and
             'point_kind' not in snapshot and 'natural_stop' not in snapshot,
             'SMOKE_EXACT_IMMUTABLE_SNAPSHOT_SCOPE')
        return True

    def label(self, target, natural_stop=None):
        need(type(target) is int and target in CUTS and natural_stop is None,
             'SMOKE_REGISTERED_CUT_NOT_NATURAL_STOP')
        return 's' + str(target) + 't'

    def build(self, cas, snapshot_ref, collection, destination, *, expected, setting):
        self._roster(setting, cas.verify_snapshot(snapshot_ref, expected=expected))
        return self._build(cas, snapshot_ref, collection, destination, expected=expected, setting=setting)

    def verify_input(self, destination, *, expected_policy_sha, trajectory, setting):
        row = self._row(trajectory, setting)
        policy = self._verify(destination, expected_policy_sha=expected_policy_sha,
                              trajectory=trajectory, setting=setting)
        need(policy['pins']['manifest'] == self.sha and policy['target_tokens'] in CUTS and
             set(policy['worker_to_native_input_role']) == set(row['roles']) and
             'point_kind' not in policy and 'natural_stop' not in policy,
             'SMOKE_EXACT_FROZEN_FINAL_INPUT_SCOPE')
        return policy

    def bind_queue(self, queue):
        need(type(queue) is FinalQueue and queue.manifest == self.sha and queue.cap == 12 and
             not hasattr(queue, '_smoke_scope_sha256'), 'SMOKE_ORIGINAL_QUEUE_ONCE')
        for name in ('enqueue', 'claim'):
            setattr(queue, name, MethodType(_bind_globals(getattr(FinalQueue, name), verify_input=self.verify_input), queue))
        queue._smoke_scope_sha256 = self.sha
        return queue

    def bind_capacity(self, capacity):
        need(type(capacity) is ModelCapacity and capacity.global_cap == 96 and capacity.aux_cap == 16 and
             not hasattr(capacity, '_smoke_scope_sha256'), 'SMOKE_ORIGINAL_SHARED_CAPACITY_ONCE')
        scope = self
        def register(owner, binding, *, authorize):
            scope._row(binding.get('trajectory'), binding.get('setting'))
            need(binding.get('manifest_sha256') == scope.sha and type(binding.get('target_tokens')) is int and
                 binding['target_tokens'] in CUTS and 'point_kind' not in binding and
                 'natural_stop' not in binding, 'SMOKE_EXACT_FINAL_CAPACITY_SCOPE')
            return scope._register(owner, binding, authorize=authorize)
        capacity.register_scope = MethodType(register, capacity)
        capacity.pause = MethodType(self._pause, capacity)
        capacity._smoke_scope_sha256 = self.sha
        return capacity

    def audit_three(self, aux_root, runs, **scope):
        self._row(scope['trajectory'], scope['setting'])
        need(scope.get('natural_stop') is None and type(scope['target_tokens']) is int and
             scope['target_tokens'] in CUTS, 'SMOKE_EXACT_K3_AUDIT_SCOPE')
        return self._audit(aux_root, runs, **scope)

    def install_exact_label_abi(self, engine, code, *, target):
        """Original exact-label adapter body, no fabricated NATURAL_STOP identity."""
        from r16_natural_contract import install_exact_label_abi
        self.label(target)
        original = _bind_globals(install_exact_label_abi, label=lambda value, meta: self.label(value))
        original(engine, code, {'actual_tokens': target})

    def final_binding(self, model_policy, *, model_policy_sha256, trajectory,
                      input_root, input_policy_sha256, replicate_index, authorize,
                      replicate_attempt=1, point_id=None):
        """Original FinalBinding, exact canonical contract SHA and real arm row.

        The internal profile projection is not a second canonical manifest. Its
        pure compiler returns THIS public contract identity; no existing account
        or queue digest is rewritten. Sampling and original host RNG unchanged.
        """
        from final_binding import FinalBinding
        from scientific_profile import SearchProfile, RNG_POLICY_SHA
        from new_scope_profile import expanded_action_seed, SMOKE_CUTS
        need(trajectory in self.rows and digest(model_policy) == model_policy_sha256,
             'SMOKE_EXACT_ORIGINAL_FINAL_MODEL_POLICY')
        protocol = copy.deepcopy(self.contract['v2_baseline_reference_protocol'])
        need(protocol['rng_policy'] == RNG_POLICY_SHA and
             protocol['model_configuration'] == model_policy_sha256,
             'SMOKE_FINAL_ORIGINAL_RNG_AND_MODEL_PINS')
        projection = {'root': self.rows[trajectory]['root'], 'protocol': protocol,
                      'new_scope_contract': copy.deepcopy(self.contract)}
        compiled = {'manifest_sha256': self.sha,
                    'trajectories': [{**copy.deepcopy(row), 'setting': row['arm'],
                                      'seed': row['search_seed']} for row in self.rows.values()]}
        def profile(manifest, policy, policy_sha):
            need(digest(manifest) == self.sha and manifest == self.contract,
                 'SMOKE_FINAL_CANONICAL_CONTRACT_NOT_LEGACY_MANIFEST')
            def compile_exact(value):
                need(value is projection, 'SMOKE_FINAL_EXACT_INFRASTRUCTURE_PROJECTION')
                return copy.deepcopy(compiled)
            result = SearchProfile.__new__(SearchProfile)
            _bind_globals(SearchProfile.__init__, compile_manifest=compile_exact)(
                result, projection, policy, policy_sha)
            return result
        result = FinalBinding.__new__(FinalBinding)
        _bind_globals(FinalBinding.__init__, SearchProfile=profile,
                      verify_input=self.verify_input)(result, self.contract, model_policy,
            model_policy_sha256, trajectory=trajectory, input_root=input_root,
            input_policy_sha256=input_policy_sha256, replicate_index=replicate_index,
            authorize=authorize, replicate_attempt=replicate_attempt, point_id=point_id)
        roles = {role for row in self.rows.values() for role in row['roles']}
        rng = expanded_action_seed(roles, checkpoints=SMOKE_CUTS)
        result.bind_request = MethodType(_bind_globals(FinalBinding.bind_request, action_seed=rng), result)
        return result


    def _snapshot_roster(self, snapshot):
        need(snapshot['trajectory'] in self.rows, 'SMOKE_SNAPSHOT_REGISTERED_TRAJECTORY')
        return self._roster(self.rows[snapshot['trajectory']]['arm'], snapshot)

    def bind_cas(self, cas):
        need(type(cas) is CAS and not hasattr(cas, '_smoke_scope_sha256'),
             'SMOKE_ORIGINAL_CAS_ONCE')
        cas.verify_snapshot = MethodType(self._snapshot_verify, cas)
        cas._smoke_scope_sha256 = self.sha
        return cas

    def seal_writer_evidence(self, core, fence, *, roles, membership_token):
        """Seal actual same-core frozen control; caller cannot provide a roster.

        CAS proof is historical evidence only. This call alone requires live
        original fence coverage and the original closed membership epoch.
        """
        from native_writer_fence import NativeWriterFence
        from original_relay_core import OriginalRelayCore
        from anonymous_roster_journal import AnonymousRosterJournal, snapshot as anonymous_snapshot
        from dynteam_membership_fence import MembershipFence
        need(type(core) is OriginalRelayCore and type(fence) is NativeWriterFence and
             core.ledger is fence.ledger and core.cas is fence.cut.cas and
             digest(core.contract) == self.sha and fence.t in self.rows and
             core.cas._smoke_scope_sha256 == self.sha,
             'SMOKE_WRITER_SAME_ORIGINAL_CORE_AND_CAS')
        t = fence.t
        self._row(t, self.rows[t]['arm'])
        membership = core.membership_fences[t]
        journal = core.journals[t]
        need(type(membership) is MembershipFence and type(journal) is AnonymousRosterJournal and
             journal.lifecycle_complete and journal.arm == self.rows[t]['arm'],
             'SMOKE_ACTUAL_MEMBERSHIP_AND_DURABLE_BIRTH_CONTROL')
        membership.verify_after_original_capture(membership_token)
        fence.verify_capture(fence.cut, roles)
        with core.ledger.mutex:
            frontier = copy.deepcopy(core.ledger.frontier(t))
            birth_control = {'epoch': core.roles.epoch,
                'births': {r: v for (trajectory, r), v in core.roles.births.items() if trajectory == t},
                'held': sorted(r for trajectory, r in core.roles.held if trajectory == t)}
        need(frontier['state'] == 'DRAINING' and frontier['generation'] == membership_token['original_generation'] and
             frontier['reserved'] == frontier['unresolved'] == frontier['active_operations'] == 0 and
             set(frontier['roles']) == set(self.rows[t]['roles']),
             'SMOKE_WRITER_ORIGINAL_DRAINED_LEDGER_FRONTIER')
        anonymous = anonymous_snapshot(journal.projection)
        need(set(anonymous['roles']) == set(self.rows[t]['roles']) and
             set(anonymous['live']) == set(birth_control['births']) and
             all(anonymous['live'][r]['birth'] == birth
                 for r, birth in birth_control['births'].items()),
             'SMOKE_ORIGINAL_DURABLE_BIRTH_AND_ROLE_GATE_AGREE')
        proof = strict(core.cas.resolve(fence.receipt).read_bytes())
        participants = copy.deepcopy(fence.participants)
        need(proof['participants'] == sorted(participants) and
             proof['participants_sha256'] == digest(participants) and
             proof['roles'] == sorted(self.rows[t]['roles']) and
             proof['cut'] == fence.cut.cut and proof['cut_sha256'] == fence.cut.cut_sha,
             'SMOKE_ACTUAL_FROZEN_WRITER_PROOF_MATCHES_CONTROL')
        value = {'schema': 'count14-dynteam-sealed-writer-control-v1',
            'contract_sha256': self.sha, 'trajectory': t, 'cut': copy.deepcopy(fence.cut.cut),
            'writer_receipt': copy.deepcopy(fence.receipt), 'roles': sorted(self.rows[t]['roles']),
            'participants': participants, 'domains_sha256': fence.domains_sha,
            'domain_bindings': [d.binding_sha for d in fence.domains],
            'membership_token': copy.deepcopy(membership_token),
            'original_ledger_frontier': frontier, 'original_role_gate': birth_control,
            'original_anonymous_birth_control': anonymous}
        membership.verify_after_original_capture(membership_token)
        fence.verify_capture(fence.cut, roles)
        need(anonymous_snapshot(journal.projection) == anonymous,
             'SMOKE_DURABLE_BIRTH_CONTROL_CHANGED_DURING_SEAL')
        with core.ledger.mutex:
            current = {'epoch': core.roles.epoch,
                'births': {r: v for (trajectory, r), v in core.roles.births.items() if trajectory == t},
                'held': sorted(r for trajectory, r in core.roles.held if trajectory == t)}
            need(current == birth_control, 'SMOKE_ROLE_CONTROL_CHANGED_DURING_SEAL')
        reference = core.cas.store_bytes(wire(value))
        with core.ledger.tx():
            core.ledger.event(t, 'DYNTEAM_ORIGINAL_WRITER_CONTROL_SEALED',
                {'cut_sha256': fence.cut.cut_sha, 'writer_receipt_sha256': fence.receipt['sha256'],
                 'control_sha256': reference['sha256'], 'membership_epoch': membership_token['membership_epoch']})
        return reference

    def _sealed_participants(self, cas, snapshot, proof):
        self._snapshot_roster(snapshot)
        value = sha(snapshot['pins'].get('native_writer_control'))
        path = cas.objects / value
        need(path.stat().st_size <= 1024 * 1024, 'SMOKE_SEALED_CONTROL_BOUND')
        control = strict(cas.resolve({'size': path.stat().st_size, 'sha256': value}).read_bytes())
        fields = {'schema', 'contract_sha256', 'trajectory', 'cut', 'writer_receipt', 'roles',
                  'participants', 'domains_sha256', 'domain_bindings', 'membership_token',
                  'original_ledger_frontier', 'original_role_gate', 'original_anonymous_birth_control'}
        need(type(control) is dict and set(control) == fields and
             control['schema'] == 'count14-dynteam-sealed-writer-control-v1' and
             control['contract_sha256'] == self.sha and control['trajectory'] == snapshot['trajectory'] and
             control['cut'] == proof['cut'] and control['roles'] == sorted(snapshot['roles']) and
             control['writer_receipt']['sha256'] == snapshot['pins']['native_writer_fence'],
             'SMOKE_SEALED_CONTROL_EXACT_CUT_AND_PROOF')
        need(strict(cas.resolve(control['writer_receipt']).read_bytes()) == proof,
             'SMOKE_SEALED_CONTROL_ORIGINAL_PROOF_BYTES')
        participants = control['participants']
        need(type(participants) is dict and participants and
             digest(participants) == proof['participants_sha256'] and
             sorted(participants) == proof['participants'] and
             control['domains_sha256'] == proof['domains_sha256'] and
             control['domain_bindings'] == proof['domain_bindings'],
             'SMOKE_SEALED_ACTUAL_PARTICIPANTS_AND_DOMAINS')
        for identity in participants.values():
            need(type(identity) is dict and set(identity) == {'pid', 'start_ticks', 'boot_id'} and
                 type(identity['pid']) is int and identity['pid'] > 0 and
                 type(identity['start_ticks']) is int and identity['start_ticks'] > 0 and
                 type(identity['boot_id']) is str and identity['boot_id'],
                 'SMOKE_SEALED_PARTICIPANT_ORIGINAL_PROCESS_IDENTITY')
        token, frontier = control['membership_token'], control['original_ledger_frontier']
        need(token['original_generation'] == snapshot['generation'] and
             token['native_membership_admission_closed'] is True and token['pending_native_effects'] == 0 and
             token['full_static_role_catalogue_sha256'] == digest(self.rows[snapshot['trajectory']]['role_kinds']) and
             frontier['trajectory'] == snapshot['trajectory'] and frontier['generation'] == snapshot['generation'] and
             frontier['target'] == snapshot['target_tokens'] and frontier['manifest_sha256'] == self.sha and
             frontier['state'] == 'DRAINING' and frontier['actual'] == snapshot['actual_search_tokens'] and
             frontier['shortfall'] == snapshot['shortfall'] and set(frontier['roles']) == set(snapshot['roles']) and
             frontier['reserved'] == frontier['unresolved'] == frontier['active_operations'] == 0,
             'SMOKE_SEALED_MEMBERSHIP_AND_ORIGINAL_LEDGER_CUT')
        born = control['original_role_gate']['births']
        anonymous = control['original_anonymous_birth_control']
        from anonymous_roster_journal import restore
        projection = restore(anonymous)
        need(set(born) == set(anonymous['live']) and set(born) <= set(snapshot['roles']) and
             anonymous['roles'] == self.rows[snapshot['trajectory']]['role_kinds'] and
             anonymous['complete_history'] is True and
             all(anonymous['live'][r]['birth'] == birth
                 for r, birth in born.items()),
             'SMOKE_SEALED_ORIGINAL_BIRTH_CONTROL_SCOPE')
        import sqlite3
        db = sqlite3.connect(cas.resolve(snapshot['durable_ledger']).as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            rows = db.execute("SELECT seq,metadata FROM events WHERE trajectory=? AND kind='DYNTEAM_ORIGINAL_WRITER_CONTROL_SEALED'",
                              (snapshot['trajectory'],)).fetchall()
        finally:
            db.close()
        wanted = {'cut_sha256': proof['cut_sha256'],
                  'writer_receipt_sha256': snapshot['pins']['native_writer_fence'],
                  'control_sha256': value, 'membership_epoch': token['membership_epoch']}
        matched = [seq for seq, raw in rows if strict(raw) == wanted]
        need(len(matched) == 1 and control['original_ledger_frontier']['sequence'] < matched[0] <= snapshot['ledger_frontier'],
             'SMOKE_SEALED_CONTROL_BOUND_TO_ORIGINAL_DURABLE_LEDGER_EVENT')
        backends = proof.get('backend_services', [])
        need(all(name in participants for name in backends), 'SMOKE_SEALED_REAL_BACKEND_PARTICIPANTS')
        return sorted(set(participants) - set(backends))

    def verify_sealed_writer_proof(self, cas, snapshot):
        return self._sealed(cas, snapshot)
