"""Actual exact-class paid custody/hydration entry, HELD and non-runtime only.

This implements an existing-database/control layer, NOT complete whole-owner
cold continuation. No fresh owner/core/layout/epoch/SDK constructor is called.
No native handle, birth, gate, ready state or global-cut proof is fabricated.
"""
from dataclasses import asdict
from pathlib import Path
from types import MethodType
import copy
import hashlib
import os

from paid_cold_material import (SCHEMA, ColdScope, PaidColdWait, digest, existing,
    need, private_read, registered_scope, sha, strict, verify_ended, verify_full_domain,
    verify_tracks, wire)
from paid_cold_attach import attach_existing_pair, quarantine_methods, sqlite_state_pin

SOURCE_PINS = dict(
    budget='a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
    final_queue='7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c',
    snapshot='00fa9154d71db4434fa8b2b9c273f69ba8a36facb2a2e45b9f85709dca12c5f8',
    native_cold_owner='22af3bfe52f711ee27bb4e523ed8ab13d375528b05f927afcb64c921095b5ddf',
    original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
    native_peer_registry='0986b61a7c71b6745442b9c71dfc67d79eebf960a50523ea1e2b5ee0f37d019d',
    dynteam_sessions='c80000d66a4958a3c2d5854d188242806ef305aaee73d2be879571e31c3909dd')

GAPS = (
    'TRUSTED_NORMAL_WHOLE_OWNER_HANDOFF_CONTROL_PRODUCER_AND_AUTHORITY_NOT_WIRED',
    'PER_TRACK_OUTER_SNAPSHOT_INTEGRITY_IS_NOT_ORIGINAL_NATIVE_WRITER_OR_GLOBAL_COHORT_PROOF',
    'ORIGINAL_ROLE_GATE_MEMBERSHIP_SPAWN_ANONYMOUS_JOURNALS_NOT_HYDRATED',
    'RESTORED_FULL_USED_PRODUCER_LIVE_APPEND_ADOPTION_NOT_IMPLEMENTED',
    'ORIGINAL_LAYOUT_NEW_CUSTODIAN_WORKSPACE_SERVICE_CAS_RUNTIME_ADOPTION_NOT_IMPLEMENTED',
    'ORIGINAL_CLI_EPOCH_PEER_KERNEL_TOOL_AND_PHYSICAL_HTTP_CUSTODY_NOT_HYDRATED',
    'ORIGINAL_STRICT_OPAQUE_SDK_LOAD_HOST_ACK_COLLABORATION_ONCE_NOT_CONNECTED',
    'ORIGINAL_ACTIVE_BUDGET_TESTER_IDLE_RACING_CLOCKS_RESOURCES_NOT_HYDRATED',
    'APPROVED_CARRIER_DOMAIN_ALL_EFFECTIVE_READER_CAPACITY_ALLOWANCE_TERMINAL_GRAPH_NOT_HYDRATED',
    'ORIGINAL_ALL_ROLE_GATE_WRITER_RESUME_NOT_CONNECTED')


def verify_original_sources():
    import importlib
    for name, pin in SOURCE_PINS.items():
        module = importlib.import_module(name)
        p = Path(module.__file__)
        need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
             hashlib.sha256(p.read_bytes()).hexdigest() == pin, 'PAID_COLD_EXACT_ORIGINAL_CLASS_SOURCE_PINS')
    return dict(SOURCE_PINS)


def verify_snapshot_outer(cas_home, control, scope, accounts, ledger_db):
    """Existing CAS.resolve + COMMITTED row/outer identity only, NOT full proof.

    The original scoped CAS.verify_snapshot/native writer proof adapters are a
    remaining runtime binding. No method is silently weakened or called with a
    synthetic verifier. L1 capability bytes are verified unchanged and retained.
    """
    from snapshot import CAS, SHARED
    home = existing(cas_home, directory=True, private=True)
    cas = CAS.__new__(CAS)
    cas.home = home
    cas.objects, cas.stage, cas.refs = home/'objects', home/'staging', home/'snapshots'
    for p in (cas.objects, cas.stage, cas.refs):
        existing(dict(path=str(p), **__import__('paid_cold_material').stamp(p.lstat())),
                 directory=True, private=True)
    snapshots = {}
    for t, row in scope.rows.items():
        track = control['tracks'][t]
        ref = track['snapshot']
        snap = strict(cas.resolve(ref).read_bytes())
        account = accounts[t]
        import json
        target = json.loads(account['targets'])[account['stage']]
        committed = ledger_db.execute('SELECT ref_sha,target FROM snapshots WHERE trajectory=? AND generation=?',
                                      (t, account['generation'])).fetchone()
        need(snap['schema'] == 'count14-agensh-snapshot-v1' and
             snap['trajectory'] == t and snap['generation'] == account['generation'] and
             snap['target_tokens'] == target and snap['actual_search_tokens'] == account['actual'] and
             snap['shortfall'] == target-account['actual'] and
             snap['pins']['manifest'] == scope.canonical_sha256 and
             set(snap['roles']) == set(row['roles']) and set(snap['shared']) == SHARED and
             snap['reserved'] == snap['unresolved'] == snap['active_operations'] == 0 and
             snap['restore'] == {'level':'L1', 'cold_continuation_supported':False} and
             snap['automatic_next_stage'] is False and committed is not None and
             committed['ref_sha'] == ref['sha256'] and committed['target'] == target,
             'PAID_COLD_ORIGINAL_COMMITTED_OUTER_SNAPSHOT_IDENTITY_NO_L1_UPGRADE')
        # Original opaque archive refs/hash verification only. No tar/SDK/PKL
        # decoding, extraction, service mutation, re-capture or enqueue.
        for role in snap['roles'].values():
            need(set(role) == {'workspace','session'}, 'PAID_COLD_ORIGINAL_ROLE_SNAPSHOT_COMPONENTS')
            for item in role.values():
                cas.resolve(item['archive'])
        for item in snap['shared'].values():
            cas.resolve(item['archive'])
        cas.resolve(snap['durable_ledger'])
        if snap['parent'] is not None:
            cas.resolve(snap['parent'])
        snapshots[t] = copy.deepcopy(snap)
    return cas, snapshots


def consume_intent(owner_home, handoff, handoff_sha256, new_birth):
    """Append-only separate control; never edit old owner/ledger/snapshot bytes."""
    root = owner_home/'paid-cold-restore-control-v1'
    root.mkdir(mode=0o700, parents=False, exist_ok=False) # no repeated consumption/retry
    path = root/'consume-intent.json'
    body = dict(schema='count14-paid-cold-held-custody-consume-intent-v1',
        handoff_sha256=handoff_sha256, old_owner_sha256=digest(handoff['old_owner']),
        new_owner=asdict(new_birth), old_epoch=handoff['old_epoch'], new_epoch=handoff['new_epoch'],
        requests_replayed=0, ledger_rewrites=0, initial_entries_replayed=0,
        runtime_ready=False, whole_paid_restore_implemented=False)
    raw = wire(body)
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    for p in (root, owner_home):
        fd = os.open(p, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


class PaidColdCustody:
    def __init__(self, handoff, handoff_sha256, scope):
        from native_peer_registry import process_birth
        verify_original_sources()
        need(type(scope) is ColdScope and digest(scope.contract) == scope.canonical_sha256 and
             handoff['schema'] == SCHEMA and handoff['contract_sha256'] == scope.canonical_sha256 and
             set(handoff) == {'schema','contract_sha256','contract','old_owner','old_epoch','new_epoch',
                 'owner_home','ledger','queue','cas_home','control_locks','children','publishers','control'},
             'PAID_COLD_EXACT_HELD_HANDOFF_SCHEMA_AND_SCOPE')
        if scope.qualification_only:
            need(all(t.startswith('OWN-') and any(p.startswith('OWN-') for p in Path(r['root']).parts)
                     for t, r in scope.rows.items()), 'PAID_COLD_OWN_FIXTURE_CANNOT_ATTACH_REAL_ROOT')
        else:
            registered_scope(scope.contract, scope.canonical_sha256)
        self.birth = process_birth(os.getpid()) # actual new OS identity, never supplied by caller
        verify_ended(handoff, self.birth)
        owner_home = existing(handoff['owner_home'], directory=True, private=True)
        need(owner_home == Path(scope.contract['arms'][0]['root'])/'owner',
             'PAID_COLD_PRESERVE_ORIGINAL_OWNER_ROOT_NO_FRESH_ROOT')
        need(Path(handoff['cas_home']['path']) == owner_home/'cas', 'PAID_COLD_EXISTING_ORIGINAL_CAS_ROOT_ONLY')
        self.pair, self.owner = None, None
        self.scope, self.handoff_sha256 = scope, sha(handoff_sha256)
        self.gaps = GAPS
        self.state = 'VERIFYING_EXISTING_PAID_CONTROL'
        control_path = existing(handoff['control']['identity'], private=True)
        need(control_path.is_relative_to(owner_home), 'PAID_COLD_PROTECTED_CONTROL_INSIDE_ORIGINAL_OWNER_HOME')
        control, self.control_sha256 = private_read(control_path, handoff['control']['sha256'])
        need(control['schema'] == 'count14-paid-cold-held-control-candidate-v1' and
             control['contract_sha256'] == scope.canonical_sha256 and
             control['old_owner_sha256'] == digest(handoff['old_owner']) and
             control['whole_cohort_cut_qualified'] is False,
             'PAID_COLD_PROTECTED_CANDIDATE_CANNOT_CLAIM_GLOBAL_CUT')
        self.control = control
        try:
            self.pair, accounts = attach_existing_pair(handoff, scope, control, self.birth)
            used, binding = verify_full_domain(owner_home, control, scope, handoff['old_owner'])
            sessions = verify_tracks(control, scope, used, binding)
            cas, snapshots = verify_snapshot_outer(handoff['cas_home'], control, scope, accounts, self.pair.ledger.db)
            existing(handoff['control']['identity'], private=True)
            private_read(control_path, handoff['control']['sha256'])
            verify_ended(handoff, self.birth) # after all locks/DB/source/control checks
            self.intent = consume_intent(owner_home, handoff, self.handoff_sha256, self.birth)
            self._hydrate_held(owner_home, handoff, accounts, sessions, used, cas, snapshots)
            need(sqlite_state_pin(self.pair.ledger.db) == handoff['ledger']['state_pin'] and
                 sqlite_state_pin(self.pair.queue.db) == handoff['queue']['state_pin'],
                 'PAID_COLD_HYDRATION_NO_LEDGER_QUEUE_ROW_OR_SCHEMA_CHANGE')
            self.state = 'PAID_COLD_EXACT_TYPED_CUSTODY_HELD_RUNTIME_UNHYDRATED_WAIT'
        except BaseException:
            self.state = 'PAID_COLD_PARTIAL_CONTROL_RETAINED_NO_RETRY'
            if self.pair is not None:
                self.pair.release_failed_pre_runtime_attach()
            raise

    def _hydrate_held(self, owner_home, handoff, accounts, sessions, used, cas, snapshots):
        from native_cold_owner import NativeColdOwner
        from original_relay_core import OriginalRelayCore
        # These are original types, NOT proxies or replacement financial core.
        # They are explicitly partial: original executable authority is disabled.
        core = OriginalRelayCore.__new__(OriginalRelayCore)
        owner = NativeColdOwner.__new__(NativeColdOwner)
        core.ledger, core.queue, core.home = self.pair.ledger, self.pair.queue, owner_home
        core.contract, core.rows = copy.deepcopy(self.scope.contract), copy.deepcopy(self.scope.rows)
        core.qualification_only, core.closed = self.scope.qualification_only, False
        core.errors, core.scientific_activation_qualified = [], False
        core.control = None # no fake native endpoint, peer or original handle
        core.sessions, core.cas = sessions, cas
        domain = next(iter(sessions.tracks.values())).domain
        with domain.lock:
            need(not domain.used, 'PAID_COLD_ONLY_NEW_EMPTY_DOMAIN_HYDRATION')
            domain.used.update(used) # hydrate NEW domain only; never clear old used
        for t, track in sessions.tracks.items():
            with track._lock:
                track._current.update({(t, role): tuple(value)
                    for role, value in self.control['tracks'][t]['session_affinity'].items()})
        core.paid_restored_control_candidate = copy.deepcopy(self.control)
        core.paid_original_snapshots = snapshots
        core.paid_old_owner_birth, core.paid_new_owner_birth = copy.deepcopy(handoff['old_owner']), self.birth
        core.paid_cold_restore_custody = self
        owner.core, owner.ledger, owner.layout, owner.bootstrap = core, core.ledger, None, None
        owner.errors, owner.state = [], 'PAID_COLD_CUSTODY_HELD_NOT_FRESH_NOT_RUNTIME_READY'
        owner.paid_cold_restore_custody = self
        quarantine_methods(core, OriginalRelayCore)
        quarantine_methods(owner, NativeColdOwner)
        quarantine_methods(cas, type(cas)) # opaque source objects cannot be overwritten by this stage
        # No instance bind/end/claim can advance a reconstructed mapping before
        # real role/custody + live producer adoption have been implemented.
        from dynteam_sessions import AffinityDomain, DynamicSessions
        quarantine_methods(domain, AffinityDomain)
        for track in sessions.tracks.values():
            quarantine_methods(track, DynamicSessions)
        owner.public = MethodType(lambda bound: self.public(), owner)
        owner.poll = MethodType(lambda bound, trajectory=None: self.public(), owner)
        self.owner = owner

    def public(self):
        return dict(schema='count14-paid-cold-exact-typed-custody-PUBLIC-v1', state=self.state,
            new_owner_birth_sha256=digest(asdict(self.birth)), handoff_sha256=self.handoff_sha256,
            protected_control_sha256=self.control_sha256, contract_sha256=self.scope.canonical_sha256,
            attached_existing_ledger_queue=self.pair is not None,
            exact_typed_owner_hydrated=self.owner is not None,
            missing_runtime_bindings=list(self.gaps), runtime_ready=False,
            original_fresh_entry_EOF_path_used=False, original_L1_cold_supported=False,
            whole_paid_new_owner_restore_implemented=False, actual_cold_qualified=False,
            requests_replayed=0, ledger_rewrites=0, models_started=0)


def restore_paid_custody_owner(handoff_path, handoff_sha256):
    """Production-facing HELD entry; cannot accept the explicit OWN fixture scope."""
    handoff, actual_sha = private_read(handoff_path, handoff_sha256)
    contract_path = existing(handoff['contract']['identity'])
    # Contract is original PUBLIC code/control. Protect its raw byte pin; no task
    # files are found, traversed or supplied as source data by this entry.
    raw = contract_path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == handoff['contract']['sha256'], 'PAID_COLD_ORIGINAL_CONTRACT_FILE_PIN')
    scope = registered_scope(strict(raw), handoff['contract_sha256'])
    custody = PaidColdCustody(handoff, actual_sha, scope)
    return custody.owner
