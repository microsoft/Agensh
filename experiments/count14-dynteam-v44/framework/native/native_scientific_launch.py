"""Two-phase executable attachment to original native team, no alternate loop.

prepare_transport() starts the original HTTP relay with SEARCH held UNSENT.
OPS initializes original ACP/CLI and starts original NativeTeamOwner; attach()
binds actual CLI peers, whole-team freezer and original K3 path before a prompt
can be dispatched. start() publishes the original clock; release_search() is
called after OPS's original only-relay/readiness setup. No Docker/SSH here.
"""
from pathlib import Path
import copy, threading
from common import need,digest,hash_file,private_dir,wire,publish
from manifest import compile_manifest
from budget import Ledger
from admission_gate import AdmissionGate
from scientific_profile import SearchProfile
from scientific_relay import ScientificRelay,Bounds
from native_model_tool_parent import NativeModelToolParents
from native_cli_tool_receipt import NativeCliToolReceipts,NativeCliToolServer,cli_peer
from native_shell_context import NativeShellContexts
from native_mcp_tool_terminal import NativeMcpToolTerminal
from native_cli_callback_custody import NativeCliCallbackCustody
from native_scientific_http import NativeScientificHttpServer
from native_bridge_backup import NativeBridgeBackup
from native_git_repository_backup import NativeGitRepositoryBackup,repository_binding
from native_relay_backup import NativeRelayContinuationBackup
from native_scientific_owner import NativeScientificOwner
from native_whole_team import NativeWholeTeamRegistration,NativeWholeTeamBackupPorts
from native_team_owner import NativeTeamOwner
from native_gitea import NativeGitea
from snapshot import CAS
from final_queue import FinalQueue


def original_cli_receipts(parents):
    """One original service per shared parent index; scopes remain (track,role).

    Later batches may start while earlier tracks already have model TOOL rows.
    Reuse the service bound before those rows, never bind a new global index or
    relax the original before-first-model guard.
    """
    from native_unmanaged_cli import enabled,NativeTools
    if type(parents)is NativeTools and enabled(parents.ledger):return None
    need(type(parents)is NativeModelToolParents,'SCIENCE_LAUNCH_ORIGINAL_SHARED_PARENT_INDEX')
    if parents.cli_receipts is None:return NativeCliToolReceipts(parents)
    receipts=parents.cli_receipts
    need(type(receipts)is NativeCliToolReceipts and receipts.parents is parents
         and receipts.ledger is parents.ledger and not receipts.closed,
         'SCIENCE_LAUNCH_ORIGINAL_SHARED_RECEIPTS')
    return receipts


class NativeScientificLaunch:
    """One original trajectory; shared queue/capacity stay with unique OPS owner."""
    @classmethod
    def prepare_transport(cls, *, ledger, parents, trajectory, manifest, model_policy,
                          bounds, transport, directory, http_address, identities,
                          maximum_output):
        need(type(ledger)is Ledger and (type(parents)is NativeModelToolParents or (getattr(ledger,'native_unmanaged_cli',False) and callable(parents)))
             and parents.ledger is ledger and type(bounds)is Bounds and callable(transport),
             'SCIENCE_LAUNCH_ORIGINAL_TRANSPORT_TYPES')
        compiled=compile_manifest(manifest)
        from r16_attempt_identity import resolve_row
        row=resolve_row(manifest,trajectory);f=ledger.frontier(trajectory)
        need(f['state']=='RUNNING' and f['generation']==1
             and f['manifest_sha256']==compiled['manifest_sha256'] and f['roles']==row['roles']
             and ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',(trajectory,)).fetchone()[0]==0,
             'SCIENCE_LAUNCH_FIRSTSTART_BEFORE_ANY_PROMPT')
        need(type(identities)is dict and set(identities.values())=={(trajectory,r) for r in row['roles']},
             'SCIENCE_LAUNCH_EXACT_HTTP_ROSTER')
        root=private_dir(directory,create=True);need(not any(root.iterdir()),'SCIENCE_LAUNCH_NEW_PRIVATE_ROOT')
        result=cls();result.ledger=ledger;result.parents=parents;result.t=trajectory
        result.root=root;result.manifest=copy.deepcopy(manifest);result.manifest_sha=digest(manifest)
        result.row=copy.deepcopy(row);result.stop=threading.Event()
        gate=AdmissionGate(ledger,global_allocated_cap=manifest['scheduling']['global_gateway_cap'],
                           search_allocated_cap=manifest['scheduling']['search_cap'])
        gate.hold_startup(trajectory)
        profile=SearchProfile(manifest,model_policy,digest(model_policy))
        relay=ScientificRelay(transport,ledger,bounds,root/'continuations',model=model_policy['model'],
            max_output=maximum_output,max_inflight=len(row['roles']),
            global_allocated_cap=manifest['scheduling']['global_gateway_cap'],admission_gate=gate,
            profile=profile,tool_parents=None if getattr(ledger,'native_unmanaged_cli',False) else parents)
        http=NativeScientificHttpServer(http_address,relay,identities)
        result.http=http;result.relay=relay;result.gate=gate
        result.attached=False;result.started=False;result.released=False
        http.start();return result

    def attach(self, *, team, publication, repository_root, cas, final_queue,
               roles, pins, registered_refs, member_cap, services, backend_names,
               writer_domains, cli_peers=None, cli_socket_paths=None, shell_context_roots=None, git_front_urls=None):
        need(not self.attached,'SCIENCE_LAUNCH_ATTACH_ONCE')
        need(type(team)is NativeTeamOwner and team.started and not team.closed
             and team.ledger is self.ledger and team.parent is self.parents and team.t==self.t
             and team.roles==self.row['roles'],'SCIENCE_LAUNCH_ORIGINAL_STARTED_HELD_TEAM')
        need(type(publication)is NativeGitea and publication.ledger is self.ledger
             and publication.binding.trajectory==self.t,'SCIENCE_LAUNCH_ORIGINAL_SOURCE_PUBLICATION')
        need(type(cas)is CAS and type(final_queue)is FinalQueue
             and final_queue.manifest==self.manifest_sha
             and final_queue.cap==self.manifest['scheduling']['final_global_cap'],
             'SCIENCE_LAUNCH_ORIGINAL_SHARED_QUEUE')
        need(self.t in self.gate.startup_held and digest(self.manifest)==self.manifest_sha,
             'SCIENCE_LAUNCH_STILL_UNSENT_STARTUP_HOLD')
        need(type(roles)is dict and set(roles)==set(team.roles)
             and all(type(row)is dict and set(row)=={'workspace','session'} for row in roles.values()),
             'SCIENCE_LAUNCH_ALL_ROLE_MOUNTS')
        if not getattr(self.ledger,'native_unmanaged_cli',False):
            for mapping in (cli_peers,cli_socket_paths,shell_context_roots,git_front_urls):
                need(type(mapping)is dict and set(mapping)==set(team.roles),'SCIENCE_LAUNCH_ALL_NATIVE_SEARCH_ROLES')
        self.team=team;self.cli_servers={};self.contexts={}
        self.receipts=original_cli_receipts(self.parents)
        registration=NativeWholeTeamRegistration(team,services,backend_names=backend_names,
                                                 expected_inventory_sha256=digest(services))
        domains=tuple(writer_domains)
        self.fence=team.register_writer_domains(domains,
            expected_domains_sha256=digest(sorted(d.binding_sha for d in domains)),whole_team=registration)
        if not getattr(self.ledger,'native_unmanaged_cli',False):
            for role in team.roles:
                observed=cli_peers[role]
                need(type(observed)is dict and cli_peer(observed['pid'])==observed,
                     'SCIENCE_LAUNCH_ACTUAL_ORIGINAL_CLI_IDENTITY')
                self.receipts.register_peer((team.t,role),observed['pid'],expected_peer_sha256=digest(observed))
                context=private_dir(shell_context_roots[role],create=True)
                need(not any(context.iterdir()),'SCIENCE_LAUNCH_NEW_SHELL_CONTEXT_ROOT')
                self.contexts[role]=NativeShellContexts(self.receipts,context,(team.t,role),git_url=git_front_urls[role])
                server=NativeCliToolServer(cli_socket_paths[role],self.receipts,(team.t,role))
                self.cli_servers[role]=server;server.start()
            mcp=NativeMcpToolTerminal.from_team(self.parents,team)
            bridge=NativeBridgeBackup(team,self.receipts,self.cli_servers,roles=roles,
                                     registered_refs=registered_refs,member_cap=member_cap)
            self.relay.tool_terminal_port=NativeCliCallbackCustody(team,self.parents,self.receipts,mcp)
        else:
            # No callback listener, peer/ticket registry, shell context, model
            # parent index or tool-terminal port. All writers remain covered by
            # the original pre-exec whole-team cgroups and namespace fence.
            NativeBridgeBackup(team,None,{},roles=roles,
                registered_refs=registered_refs,member_cap=member_cap)
            bridge=team.bridge_backup
        relay_backup=NativeRelayContinuationBackup(self.relay,self.http,team.t)
        repo_root=Path(repository_root)
        git=NativeGitRepositoryBackup(publication,repo_root,registered_refs=registered_refs,
            expected_repository_binding_sha256=digest(repository_binding(repo_root,publication.binding.service_instance_sha256)),
            expected_publication_pin=hash_file(publication.home/'gitea-publication.json'))
        self.backups=NativeWholeTeamBackupPorts(registration,git,relay_backup,bridge,roles=roles)
        self.controller=NativeScientificOwner(team,self.relay,self.gate,cas,final_queue,self.root/'controller',
            setting=self.row['setting'],graph=self.backups.graph,expected_graph_sha256=self.backups.graph_sha,
            roles=roles,pins=pins,registered_refs=registered_refs,member_cap=member_cap,
            backup_ports=self.backups,http_server=self.http)
        self.attached=True;return self

    def start(self):
        need(self.attached and not self.started,'SCIENCE_LAUNCH_ATTACHED_START_ONCE')
        bindings=self.controller.start();self.started=True
        publish(self.root/'BUDGET_CLOCK_BINDINGS.json',wire(bindings))
        return bindings

    def release_search(self):
        # OPS already owns original native network/front/router readiness.
        # Never invent a worker boolean or bypass its actual namespace probes.
        need(self.started and not self.released,'SCIENCE_LAUNCH_RELEASE_ONCE_AFTER_CLOCK')
        self.controller._shared();self.team.writer_fence._coverage()
        self.gate.release_startup(self.t);self.released=True

    def run(self):
        """No new model sends; original controller drives two cuts/K3 queue."""
        need(self.started,'SCIENCE_LAUNCH_START_BEFORE_RUN')
        while not self.stop.is_set():
            status=self.controller.step()
            if status['owner_state'] in ('FINAL_PARKED','FAULT'):return status
            self.stop.wait(.1)
        return self.controller.status()
