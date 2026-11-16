"""Concrete cold composition of ORIGINAL relay/gate/profile/HTTP/queue objects.

This is the actual transport/accounting core, not a second model dispatcher.
It deliberately cannot declare scientific PREPARED or activate: native dynamic
workers, tools, complete writer fence/checkpoint/K3 ports still must be bound.
Any partial preparation remains same-object custody; no blind retry or teardown.
"""
from __future__ import annotations

from pathlib import Path
from types import FunctionType, MethodType
import json
import secrets
import time

from admission_gate import AdmissionGate
from common import need, digest, private_dir
from scientific_relay import ScientificRelay, Bounds
from native_scientific_http import NativeScientificHttpServer
from final_queue import FinalQueue
from snapshot import CAS
from dynteam_sessions import CohortSessions
from dynteam_relay_binding import install as install_affinity
from dynteam_metadata import BudgetAnchor
from dynamic_role_gate import DynamicRoleGate
from native_peer_registry import NativePeerRegistry
from native_session_control import NativeSessionInbox
from native_metadata_publisher import NativeMetadataPublisher
from anonymous_roster_journal import AnonymousRosterJournal
from new_scope_profile import original_search_profile
from native_budget_park import NativeBudgetParkProjection


def append_original_initial_100M_targets(ledger, contract):
    """Use the already verified ORIGINAL new-start 100M append body unchanged.

    Only its trusted scope/compiler callbacks bind our explicit fresh contract.
    The historical event kind contains NEW48 as an inherited serialization name;
    its authorization SHA binds THIS new paired contract, not an old experiment.
    No old root/account is opened or relabelled; costs and request rows unchanged.
    """
    need(contract['mode']=='production','DYNTEAM_PRODUCTION_100M_APPEND_NEVER_SMOKE')
    from expansion100_contract import append_new_targets
    rows = {r["trajectory_id"]: r for r in contract["trajectories"]}
    policy = dict(schema="count14-user-authorized-new-dynamic-100m-v1",
                  contract_sha256=digest(contract), trajectories=sorted(rows),
                  regular_targets=[10000000, 20000000, 50000000, 100000000])
    def exact(value):
        need(value is contract and hasattr(ledger, "_dynteam_catalogues") and
             set(ledger._dynteam_catalogues) == set(rows), "DYNTEAM_EXACT_NEW_START_100M_SCOPE")
        return policy
    original = append_new_targets
    function = FunctionType(original.__code__, dict(original.__globals__, check=exact,
        roster=lambda m: (exact(m) and rows), group=lambda m: (exact(m) and "new-4-8")),
        original.__name__, original.__defaults__, original.__closure__)
    for t in rows:
        function(ledger, contract, t)


class OriginalRelayCore:
    @classmethod
    def prepare(cls, *, ledger, contract, home, original_model_policy, original_model_policy_sha256,
                bounds, maximum_output, key_path, transport_factory, qualification_only=False, native_networks=None):
        need(type(qualification_only) is bool and type(bounds) is Bounds and callable(transport_factory),
             "DYNTEAM_ORIGINAL_RELAY_COLD_BINDINGS")
        need(qualification_only == getattr(ledger, "_dynteam_qualification_only", None),
             "DYNTEAM_NO_OWN_LEDGER_IN_PRODUCTION_CORE")
        if not qualification_only:
            need(hasattr(ledger, "_dynteam_frozen_directory_proof") and
                 ledger._dynteam_frozen_directory_proof.canonical_contract_sha256 == digest(contract) and
                 contract["racing"]["method"] == "m7" and
                 contract["racing"]["judge"] == "COUNT14_ORIGINAL_SEARCH_PUBLIC_TASK_TOOLS",
                 "DYNTEAM_PRODUCTION_FROZEN_DIRECTORY_AND_FULL_EXECUTING_RACING_REQUIRED")
        rows = {r["trajectory_id"]: r for r in contract["trajectories"]}
        from native_network_binding import NativeNetworkBinding
        need(native_networks is None and qualification_only or type(native_networks) is dict and
             set(native_networks)==set(rows), 'DYNTEAM_PRODUCTION_NATIVE_NETWORKS_REQUIRED_BEFORE_RELAY_LISTEN')
        networks={} if native_networks is None else dict(native_networks)
        for t,network in networks.items():
            need(type(network) is NativeNetworkBinding, 'DYNTEAM_TRUSTED_NATIVE_NETWORK_OBJECT')
            network.checked(contract=contract,row=rows[t],qualification_only=qualification_only)
        need(len({n.network_id for n in networks.values()})==len(networks) and
             (qualification_only or len({n.gateway for n in networks.values()})==len(networks)),
             'DYNTEAM_NETWORK_ISOLATION_NO_SHARED_TRAJECTORY_BRIDGE')
        need(contract["schema"] == "count14-dynteam-two-arm-public-contract-v1" and
             len(rows) in (2, 6) and set(rows) == set(ledger._dynteam_catalogues) and
             all(tuple(r["roles"]) == ledger._dynteam_catalogues[t] and r["request_cap"] == 13
                 for t, r in rows.items()), "DYNTEAM_ORIGINAL_CORE_EXACT_FROZEN_ROLE_GRID")
        home = Path(home)
        need(home.is_absolute() and home.resolve() == home and
             ((qualification_only and any(p.startswith("OWN-") for p in home.parts)) or
              (not qualification_only and home == Path(contract["arms"][0]["root"]) / "owner")),
             "DYNTEAM_ORIGINAL_CORE_ONLY_EXACT_NEW_SCRATCH_ROOT")
        profile = original_search_profile(contract, original_model_policy,
                                         original_policy_sha256=original_model_policy_sha256)
        need(bounds.matches_model(original_model_policy["model"]), "DYNTEAM_ORIGINAL_CORE_SAME_MODEL_PROOF")
        self = cls()
        self.ledger, self.contract, self.home = ledger, contract, private_dir(home, create=True)
        self.rows, self.profile = rows, profile
        self.qualification_only = qualification_only
        self.native_networks = networks
        self.state = "CREATING_ORIGINAL_TRANSPORT_HELD"
        self.errors = []
        self.engines, self.servers, self.journals, self.tokens = {}, {}, {}, {}
        self.queue = self.cas = None
        self.control = None
        self.clocks = {}
        self.clock_warnings = []
        self.closed = False
        # Native APIs are registered only by the actual cold launcher. Never
        # infer same-host process identity or full membership from an OWN fake.
        self.scientific_activation_qualified = False
        self.native_worker_bindings_complete = False
        try:
            self._prepare(bounds, maximum_output, key_path, transport_factory)
        except Exception as error:
            # Startup orchestration errors only: no locals, agent messages,
            # task/candidate contents, model request/response or tool bodies.
            import traceback
            self.errors.append({"PUBLIC_code": "DYNTEAM_CORE_PARTIAL_RETAINED_NO_AUTOMATIC_RETRY",
                                "exception_type": type(error).__name__,
                                "infra_exception_message": str(error),
                                "infra_traceback": traceback.format_exception(error)})
            self.state = "PARTIAL_RETAINED_NO_ACTIVATION"
        return self

    def _prepare(self, bounds, maximum_output, key_path, transport_factory):
        manifest_sha = digest(self.contract)
        self.ledger.native_unmanaged_cli = True
        # Original UNKNOWN formula/stops, plus existing v2 explicit rejection
        # and proven closed-HTTP capacity views, scoped to this new instance.
        # Health/SYSTEM probes and full AUX terminal custody remain required.
        self.ledger.enable_unknown_reservation_policy()
        from native_v2_dispositions import NativeV2Dispositions
        self.v2_dispositions=NativeV2Dispositions(self.ledger)
        need(not self.ledger.db.execute("SELECT 1 FROM accounts LIMIT 1").fetchone(),
             "DYNTEAM_CORE_FIRST_START_EMPTY_NEW_SCOPE_ACCOUNTS")
        mode=self.contract['mode']
        need((mode=='production' and len(self.rows)==6) or (mode=='smoke' and len(self.rows)==2),
             'DYNTEAM_EXACT_FORMAL_OR_SMALL_SYSTEM_SMOKE_GRID')
        expected=[10000000,20000000,50000000,100000000] if mode=='production' else [500000,1000000]
        need(all(row['checkpoints_tokens']==expected and row['search_tokens']==expected[-1]
                 for row in self.rows.values()),'DYNTEAM_RUNTIME_BUDGET_MATCHES_PREREGISTERED_MODE')
        for t, row in self.rows.items():
            if mode=='smoke':
                # The ORIGINAL Ledger already supports these two small cuts.
                # Never run the100M extension on a SYSTEM-smoke account.
                self.ledger.register(t,row['roles'],manifest_sha,targets=tuple(expected),request_cap=13)
            else:self.ledger.register(t, row["roles"], manifest_sha, request_cap=13)
        if mode=='production':append_original_initial_100M_targets(self.ledger, self.contract)
        need(all(json.loads(self.ledger.account(t)['targets'])==expected for t in self.rows),
             'DYNTEAM_ACTUAL_LEDGER_TARGETS_MATCH_CONTRACT_BEFORE_HTTP_OR_CLI')
        self.roles = DynamicRoleGate(self.ledger)
        from dynteam_membership_fence import MembershipFence
        self.membership_fences = {t:MembershipFence(racing_players=7 if r['arm']=='DYNTEAM_RACING' else 0)
                                  for t,r in self.rows.items()}
        self.pending_native_launches = {}
        self.gate = self.roles.install_cold(AdmissionGate(self.ledger, global_allocated_cap=96, search_allocated_cap=78))
        if mode=='production':
            from formal_early_sanity import FormalEarlySanity
            FormalEarlySanity(self)
        self.v2_dispositions.bind_gate(self.gate)
        for t in self.rows:
            self.gate.hold_startup(t)
        from disk_clock import start_supervised, sample_cohort_atomic
        for t in self.rows:
            projection = NativeBudgetParkProjection(self.gate, t, self.home / "clocks" / digest(t))
            self.clocks[t] = projection
            projection.sample = MethodType(sample_cohort_atomic, projection)
            start_supervised(projection, self._record_clock_warning)
        self.sessions = CohortSessions(list(self.rows), racing_trajectories=[t for t, r in self.rows.items()
                                                                          if r["arm"] == "DYNTEAM_RACING"])
        bindings = {(t, role): row["block"] for t, row in self.rows.items() for role in row["roles"]}
        self.peers = NativePeerRegistry(source_commit="70e2ca54c078597e3314755064d2ef1a83344c8e",
                                        allowed_bindings=bindings)
        self.inbox = NativeSessionInbox()
        for t, row in self.rows.items():
            path = ((self.home / "OWN-role-metadata" / t) if self.qualification_only else
                    Path(row["root"]) / "metadata")
            path = private_dir(path, create=True)
            self.journals[t] = AnonymousRosterJournal(path / "DYNTEAM_ROSTER_PUBLIC_METADATA.sqlite",
                block=row["block"], arm=row["arm"], qualification_only=self.qualification_only, lifecycle_complete=True)
            original_transport=transport_factory(t)
            engine = ScientificRelay(original_transport, self.ledger, bounds,
                private_dir(self.home / "continuations" / digest(t), create=True),
                model=self.profile.policy["model"], max_output=maximum_output, max_inflight=13,
                global_allocated_cap=96, admission_gate=self.gate, profile=self.profile)
            self.engines[t] = engine
            self.v2_dispositions.bind_engine(engine,original_transport=original_transport)
            install_affinity(engine, self.sessions, key_path=key_path)
            # One original HTTP custodian per original engine, as in v2. A
            # single engine cannot own six distinct native_http_custodian slots.
            identities = {secrets.token_urlsafe(32): (t, role) for role in row["roles"]}
            self.tokens[t] = identities
            # A native container cannot use its own loopback to reach this
            # host custodian. Bind only the registered experiment bridge's
            # gateway, not 0.0.0.0, a guessed host-gateway or the GLM address.
            host = self.native_networks[t].gateway if t in self.native_networks else '127.0.0.1'
            server = NativeScientificHttpServer((host, 0), engine, identities)
            self.servers[t] = server
            self.v2_dispositions.bind_http_custodian(server)
            server.start()
        self.publisher = NativeMetadataPublisher(inbox=self.inbox, sessions=self.sessions,
            journals=self.journals, bindings=bindings, original_control_projection=self.original_projection,
            qualification_only=self.qualification_only)
        self.cas = CAS(self.home / "cas")
        self.queue = FinalQueue(self.home / "final-queue", manifest_sha256=manifest_sha, global_cap=12)
        self.state = "ORIGINAL_TRANSPORT_HELD_NATIVE_BINDINGS_PENDING"
        from native_active_clock import NativeActiveClock
        NativeActiveClock(self)

    def original_projection(self, trajectory, role):
        # Pure original COUNT/frontier, released before anonymous-journal I/O.
        with self.ledger.mutex:
            f = self.ledger.frontier(trajectory)
            n = self.v2_dispositions.search_count(trajectory,role)
        return BudgetAnchor(f["actual"], f["sequence"], time.time_ns(), time.monotonic_ns()), n == 0

    def _record_clock_warning(self, kind, value):
        # Original publisher calls this outside gate locks. Metadata only, no
        # message/locals; an individual clock warning never stops other tracks.
        self.clock_warnings.append({"PUBLIC_code": kind, "trajectory": value.get("trajectory"),
                                    "exception_type": value.get("exception_type")})
        self.clock_warnings = self.clock_warnings[-128:]

    def bind_native_control(self, socket_path, *, child_uid, native_tool_physical_clear, archive_bindings,
                            native_socket_uid=None, native_socket_gid=None):
        """Concrete guarded bridge control on THIS same held original owner.

        SDK/cgroup tool projection and fixed native archive mounts come from the
        actual cold launcher; neither JSON callers nor OWN placeholders supply
        completion evidence. This does not release a startup/model gate.
        """
        from native_session_control import NativeSessionControl
        from native_phase_proof import NativePhaseProofInbox
        from native_bridge_protocol import NativeBridgeInbox
        from native_bridge_owner import NativeBridgeLifecycleOwner
        from native_archive_guard import NativeArchiveGuard
        from native_spawn_protocol import NativeSpawnInbox
        from native_spawn_owner import NativeSpawnOwner
        from native_session_reconnect import NativeSessionReconnectInbox
        need(self.state == 'ORIGINAL_TRANSPORT_HELD_NATIVE_BINDINGS_PENDING' and self.control is None and
             callable(native_tool_physical_clear) and
             set(archive_bindings) == {(t,r) for t,row in self.rows.items() for r in row['roles']},
             'DYNTEAM_FULL_ORIGINAL_NATIVE_CONTROL_BEFORE_ACTIVATION')
        if not self.qualification_only:
            need(Path(socket_path) == self.home/'native-control.sock', 'DYNTEAM_EXACT_NEW_OWNER_CONTROL_SOCKET')
            need(child_uid==native_socket_uid==native_socket_gid==10000,
                 'DYNTEAM_NATIVE10000_METADATA_SOCKET_ACCESS_WITHOUT_ELEVATION')
        self.phase_proof_inbox = NativePhaseProofInbox()
        self.bridge_inbox = NativeBridgeInbox()
        def physical(t, role):
            clear = native_tool_physical_clear(t,role)
            need(type(clear) is bool, 'DYNTEAM_ORIGINAL_TOOL_CUSTODY_BOOLEAN_REQUIRED')
            return dict(models_clear=self.original_projection(t,role)[1], tools_clear=clear)
        self.native_physical_projection = physical
        self.bridge_owner = NativeBridgeLifecycleOwner(self,child_uid=child_uid,
            original_physical_projection=physical,archive_guard=NativeArchiveGuard(archive_bindings))
        self.spawn_inbox=NativeSpawnInbox();self.spawn_owner=NativeSpawnOwner(self)
        self.reconnect_inbox=NativeSessionReconnectInbox()
        self.control = NativeSessionControl(socket_path,peer_validator=self.validate_native_peer,receiver=self.inbox.receive,
            phase_proof_receiver=self.phase_proof_inbox.receive,lifecycle_receiver=self.bridge_inbox.receive,
            spawn_receiver=self.spawn_inbox.receive,
            reconnect_receiver=self.reconnect_inbox.receive,
            socket_uid=native_socket_uid,socket_gid=native_socket_gid)
        self.control.start()
        return self.control

    def validate_native_peer(self,envelope,peercred):
        if self.peers.validate(envelope,peercred):return True
        registry=getattr(self,'native_containers',None)
        return registry is not None and registry.admit_initial_peer(envelope,peercred)

    def poll_native_control_once(self):
        need(self.control is not None, 'DYNTEAM_NATIVE_CONTROL_MUST_BE_BOUND')
        # Called by original owner, not a second scientific dispatcher/thread.
        # No ledger/science locks are held while publishing metadata/receipts.
        producer=getattr(self,'resource_producer',None)
        if producer is not None:producer.poll()
        resources=getattr(self,'cohort_resources',None)
        if resources is not None:resources.maybe_refresh()
        health=getattr(self,'system_health',None)
        if health is not None:health.poll()
        sanity=getattr(self,'formal_early_sanity',None)
        if sanity is not None:sanity.poll()
        # Complete metadata for effects the ORIGINAL owner already admitted,
        # including a BIRTH that predates a held cut. Never launch latent roles
        # or acquire a new lease here. Authentication must see the typed daemon
        # boot plans before it can accept the original bridge/session receipt.
        registry=getattr(self,'native_containers',None)
        if registry is not None and registry.image_ids is not None:
            for (trajectory,role),launch in list(self.pending_native_launches.items()):
                need(self.membership_fences[trajectory].owns(launch.get('lease'),role),
                     'DYNTEAM_NATIVE_BOOTSTRAP_ONLY_ALREADY_ADMITTED_MEMBERSHIP_LEASE')
                registry.sync_boot_plans(trajectory,[role])
        return (self.spawn_inbox.poll_once(self.spawn_owner.handle)+
                self.bridge_inbox.poll_once(self.bridge_owner.handle) + self.publisher.poll_once() +
                self.reconnect_inbox.poll_once(getattr(self,'native_sdk_startup_epochs',None)) +
                self.phase_proof_inbox.poll_once(sessions=self.sessions,
                    original_physical_projection=self.native_physical_projection))

    def bind_scoped_native_docker(self,docker,*,image_ids=None):
        from native_container_retirement import NativeContainerRegistry
        need(self.control is not None and not hasattr(self,'native_containers') and
             (self.qualification_only or self.native_networks and
              {n.daemon_data_root for n in self.native_networks.values()}=={str(docker.route.data_root)}),
             'DYNTEAM_COLD_NATIVE_DOCKER_MATCHES_ORIGINAL_BRIDGE_DAEMON')
        self.native_containers=NativeContainerRegistry(self,docker,image_ids=image_ids)
        return self.native_containers

    def public_state(self):
        with self.ledger.mutex:
            requests = self.ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
            settled = self.ledger.db.execute("SELECT COUNT(*) FROM requests WHERE state='SETTLED'").fetchone()[0]
        return dict(state=self.state, original_accounts=len(self.rows),
                    native_registered_slots=sum(len(r["roles"]) for r in self.rows.values()),
                    original_HTTP_listeners=len(self.servers), request_rows=requests, SETTLED=settled,
                    original_clock_publishers=len(self.clocks),
                    native_bridge_relay_listeners=len(self.native_networks),
                    exact_qualified_native_120s_reader_bound=False,
                    native_worker_bindings_complete=self.native_worker_bindings_complete,
                    scientific_activation_qualified=self.scientific_activation_qualified,
                    no_model_dispatch_loop_added=True, errors=list(self.errors))

    def close_original_transports_after_drained(self):
        need(not self.closed and self.ledger.global_unresolved() == 0,
             "DYNTEAM_ORIGINAL_CORE_PHYSICAL_MODEL_CUSTODY_RETAINED")
        # This method is not native-worker retirement. It cannot stop any peer,
        # model, tool or container, and no active bound native peer is allowed.
        need(not getattr(self, "peers", None) or not self.peers._peers,
             "DYNTEAM_CORE_NATIVE_PEERS_MUST_REMAIN_WITH_ORIGINAL_OWNER")
        health=getattr(self,'system_health',None)
        producer=getattr(self,'resource_producer',None)
        if producer is not None:
            need(producer.physical_clear(),'DYNTEAM_CORE_RESOURCE_SAMPLER_SAME_CHILD_CUSTODY_RETAINED')
        if health is not None:
            need(health.physical_clear(),'DYNTEAM_CORE_SYSTEM_PROBE_PHYSICAL_CUSTODY_RETAINED')
        if producer is not None:producer.stop_admission()
        if health is not None:
            health.stop_admission()
        if hasattr(self, "gate"):
            self.gate.shutdown()
        if self.control is not None:
            self.control.close()
        for clock in self.clocks.values():
            clock.close()
        for server in self.servers.values():
            if not server.closed:
                server.stop_listener()
                server.close_after_drained()
        for engine in self.engines.values():
            engine.close()
        for journal in self.journals.values():
            journal.close()
        if self.queue is not None:
            self.queue.close()
        self.closed = True
        self.state = "ORIGINAL_TRANSPORTS_DRAINED_NO_NATIVE_WORKERS_RETIRED"
