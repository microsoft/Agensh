"""Whole-team physical checkpoint mode (explicit trusted first-start binding).

Stop original model admission; settle accepted requests/operations; freeze ALL
worker/SDK/backend domains. Opaque filesystem copies while all writers are frozen
replace per-connection lineage and application async fixed-point proofs. This is
same-instance continuation, never cold restore or an assertion of process exit.
"""
from pathlib import Path
import copy, os, stat
from bridge import process_identity
from common import need, digest, sha, wire, private_dir, publish, hash_file

REQUIRED_SERVICES = frozenset(('gitea', 'mattermost'))
PHYSICAL_COMPONENTS = frozenset(('gitea_database', 'collaboration'))


def root_identity(path):
    p = Path(path); s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and stat.S_ISDIR(s.st_mode),
         'WHOLE_TEAM_CANONICAL_PHYSICAL_ROOT')
    return {'path': str(p), 'device': s.st_dev, 'inode': s.st_ino,
            'uid': s.st_uid, 'gid': s.st_gid}


class NativeWholeTeamRegistration:
    """Owner-supplied complete service inventory, pinned before first model.

    ``services`` maps every Gitea/MM/backend service to its original host process
    identity and ALL its persistent mount roots. ``backend_names`` is the exact
    frozen launch manifest's backend roster, not discovery from process output.
    Domains may contain entire descendant trees; individual connections are not
    enumerated, attributed or required to be empty. Control owner stays outside.
    """
    def __init__(self, owner, services, *, backend_names, expected_inventory_sha256):
        from native_team_owner import NativeTeamOwner
        need(type(owner) is NativeTeamOwner and owner.started and not owner.closed
             and owner.writer_fence is None, 'WHOLE_TEAM_BEFORE_WRITER_REGISTRATION')
        self.owner = owner; self.ledger = owner.ledger; self.t = owner.t
        need(type(backend_names) is tuple and backend_names
             and len(set(backend_names)) == len(backend_names)
             and all(type(n) is str and n.startswith('backend-') and n.isascii()
                     and all(c.isalnum() or c in '-_' for c in n) for n in backend_names),
             'WHOLE_TEAM_COMPLETE_BACKEND_ROSTER')
        need(type(services) is dict and set(services) == REQUIRED_SERVICES | set(backend_names),
             'WHOLE_TEAM_ALL_GITEA_MATTERMOST_BACKENDS')
        self.services = copy.deepcopy(services); self.backends = backend_names
        self.inventory_sha = sha(expected_inventory_sha256)
        need(digest(self.services) == self.inventory_sha, 'WHOLE_TEAM_LAUNCH_INVENTORY_PIN')
        with self.ledger.mutex:
            f = self.ledger.frontier(self.t)
            need(f['state'] == 'RUNNING' and f['generation'] == 1
                 and self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',
                                           (self.t,)).fetchone()[0] == 0,
                 'WHOLE_TEAM_BIND_BEFORE_FIRST_MODEL')
        self.current()
        with self.ledger.tx():
            registry=getattr(self.ledger,'native_whole_team_registrations',None)
            if registry is None:
                registry={};self.ledger.native_whole_team_registrations=registry
            need(type(registry)is dict and self.t not in registry,'WHOLE_TEAM_REGISTRATION_ONCE')
            self.ledger.event(self.t,'NATIVE_WHOLE_TEAM_REGISTERED',{'inventory_sha256':self.inventory_sha})
            registry[self.t]=self

    def current(self):
        need(digest(self.services) == self.inventory_sha, 'WHOLE_TEAM_INVENTORY_CHANGED')
        identities = {}
        for name, row in self.services.items():
            need(type(row) is dict and set(row) == {'process', 'roots'}
                 and type(row['process']) is dict
                 and set(row['process']) == {'pid', 'start_ticks', 'boot_id'}
                 and process_identity(row['process']['pid']) == row['process'],
                 'WHOLE_TEAM_ORIGINAL_LIVE_SERVICE')
            need(type(row['roots']) is dict and row['roots']
                 and all(type(n) is str and n.isascii() and n
                         and all(c.isalnum() or c in '-_' for c in n) for n in row['roots']),
                 'WHOLE_TEAM_ALL_SERVICE_PERSISTENT_ROOTS')
            for binding in row['roots'].values():
                need(type(binding) is dict and set(binding) == {'path','device','inode','uid','gid'}
                     and root_identity(binding['path']) == binding,
                     'WHOLE_TEAM_PHYSICAL_ROOT_REPLACED')
            identities['service:' + name] = copy.deepcopy(row['process'])
        need(len({p['pid'] for p in identities.values()}) == len(identities),
             'WHOLE_TEAM_DISTINCT_SERVICE_IDENTITIES')
        return identities

    def frozen(self, fence):
        from native_writer_fence import NativeWriterFence
        need(type(fence) is NativeWriterFence and fence.owner is self.owner
             and fence.whole_team is self and fence.state == 'PARKED',
             'WHOLE_TEAM_ORIGINAL_PARKED_FENCE')
        self.current(); fence._coverage()
        need(all(d.frozen() and d.read('cgroup.freeze').strip() == '1' for d in fence.domains),
             'WHOLE_TEAM_ALL_DOMAINS_PHYSICALLY_FROZEN')
        return self.inventory_sha


def frozen_whole_team(owner):
    """Only a real registered and currently frozen team may replace control drain."""
    fence = owner.writer_fence
    registration = getattr(fence, 'whole_team', None)
    if registration is None:
        return False
    need(type(registration) is NativeWholeTeamRegistration, 'WHOLE_TEAM_ORIGINAL_REGISTRATION')
    if fence.state != 'PARKED':
        return False
    registration.frozen(fence)
    return True


def registered_runtime_sockets(registration):
    """Only ORIGINAL native MCP/Git listener paths, not names found by scanning.

    This is metadata-only. Actual data, unregistered UDS, FIFO/devices and links
    are NOT eligible. The complete original team must remain physically frozen.
    """
    import stat
    owner=registration.owner;result={};paths=[]
    for config in getattr(owner,'configs',{}).values():
        paths.extend((*config['sockets'].values(),config['git_path']))
    # Original ACP bridge has one fixed endpoint (public bootstrap contract).
    # Require the exact preregistered router mount and role-local canonical root.
    for role in owner.roles:
        row=registration.services.get('backend-router-'+role)
        if row is None:continue
        expected=owner.root.parent/'host-workers'/role/'acp'
        if any(Path(binding['path'])==expected for binding in row['roots'].values()):
            paths.append(expected/'agent.sock')
    for path in paths:
        path=Path(path);s=path.lstat()
        need(path.resolve()==path and stat.S_ISSOCK(s.st_mode),'WHOLE_TEAM_REGISTERED_IPC_NOT_SOCKET')
        result[str(path)]=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_mtime_ns)
    return result

class NativeWholeTeamPhysicalBackup:
    """Opaque crash-consistent physical roots, including WAL and backend data.

    No SQL request is sent to a frozen server. CAS's existing no-follow stable-fd
    traversal makes complete root archives (including original mtimes). Embedded
    archives retain actual bytes in the normal snapshot closure, not loose refs.
    Original Git export, relay SQLite backup and bridge producers are reused.
    """
    def __init__(self, registration, *, component, service_names):
        need(type(registration) is NativeWholeTeamRegistration
             and component in PHYSICAL_COMPONENTS, 'WHOLE_TEAM_PHYSICAL_COMPONENT')
        need(type(service_names) is tuple and service_names
             and len(set(service_names)) == len(service_names)
             and set(service_names) <= set(registration.services),
             'WHOLE_TEAM_PHYSICAL_SERVICE_COVERAGE')
        if component == 'gitea_database':
            need(service_names == ('gitea',), 'WHOLE_TEAM_GITEA_PHYSICAL_ROOTS')
        else:
            need(set(service_names) == {'mattermost', *registration.backends},
                 'WHOLE_TEAM_COLLAB_ALL_BACKEND_ROOTS')
        self.registration = registration; self.component = component; self.names = service_names
        self.protocol = {'schema': 'agensh-whole-team-physical-copy-v1',
                         'implementation_sha256': hash_file(Path(__file__))['sha256'],
                         'no_live_database_rpc': True, 'whole_team_inventory': registration.inventory_sha}
        self.graph_domain = {'instance_sha256': digest({'inventory': registration.inventory_sha,
                                                       'services': list(service_names)}),
                             'backup_protocol_sha256': digest(self.protocol), 'objects': [component]}
        self.captures = {}

    def run(self, cut, destination):
        r = self.registration; r.frozen(cut.writer_fence)
        need(cut.writer_owner is r.owner and cut.graph[self.component] == self.graph_domain
             and self.component not in cut.receipts and cut.cut_sha not in self.captures,
             'WHOLE_TEAM_PHYSICAL_SAME_CUT_ONCE')
        cut.current({'DRAINING'})
        dest = private_dir(destination, create=True)
        need(not any(dest.iterdir()), 'WHOLE_TEAM_PHYSICAL_NEW_DESTINATION')
        object_root = private_dir(dest / self.component, create=True); roots = []
        try:
            for service in self.names:
                for name, binding in sorted(r.services[service]['roots'].items()):
                    # No candidate/database text is decoded or published.
                    r.frozen(cut.writer_fence)
                    sockets=registered_runtime_sockets(r)
                    archive = cut.cas.capture_tree(Path(binding['path']),runtime_sockets=sockets)
                    target = object_root / (service + '--' + name + '.tar.gz')
                    need(not target.exists(), 'WHOLE_TEAM_UNIQUE_PHYSICAL_ARCHIVE')
                    with cut.cas.resolve(archive['archive']).open('rb') as src, target.open('xb') as out:
                        import shutil
                        shutil.copyfileobj(src, out, 1024 * 1024); out.flush(); os.fsync(out.fileno())
                    target.chmod(0o400)
                    need(hash_file(target) == archive['archive'], 'WHOLE_TEAM_ARCHIVE_BYTES')
                    roots.append({'service': service, 'name': name,
                                  'root_binding_sha256': digest(binding), 'object': archive})
            r.frozen(cut.writer_fence)
            receipt = {'schema': 'agensh-whole-team-physical-backup-v1',
                       'cut_sha256': cut.cut_sha, 'inventory_sha256': r.inventory_sha,
                       'whole_team_frozen': True, 'roots': roots, 'live_sql_rpc': False,
                       'runtime_socket_policy': 'REGISTERED_NATIVE_MCP_GIT_AND_ACP_AGENT_SOCK_ONLY',
                       'actual_copy_implementation_sha256':hash_file(Path(__file__))['sha256']}
            publish(object_root / 'PHYSICAL_ROOTS.json', wire(receipt))
            native = cut.cas.store_bytes(wire(receipt))
            result = cut.record_native_backup(self.component, {self.component: object_root},
                {'cut_sha256': cut.cut_sha, 'instance_sha256': self.graph_domain['instance_sha256'],
                 'backup_protocol_sha256': self.graph_domain['backup_protocol_sha256'],
                 'receipt_sha256': native['sha256']})
            self.captures[cut.cut_sha] = {'service_receipt': result, 'native_receipt': native}
            return self.captures[cut.cut_sha]
        except BaseException:
            r.ledger.latch_fault(r.t, 'WHOLE_TEAM_PHYSICAL_BACKUP_FAILED_NO_RETRY')
            raise


class NativeWholeTeamBackupPorts:
    """One direct whole-freeze producer set; no async SQL or new proof gate."""
    def __init__(self, registration, git, relay, bridge, *, roles):
        from native_git_repository_backup import NativeGitRepositoryBackup
        from native_relay_backup import NativeRelayContinuationBackup
        from native_bridge_backup import NativeBridgeBackup
        need(type(registration) is NativeWholeTeamRegistration
             and type(git) is NativeGitRepositoryBackup
             and type(relay) is NativeRelayContinuationBackup
             and type(bridge) is NativeBridgeBackup, 'WHOLE_TEAM_ORIGINAL_BACKUP_PORTS')
        self.registration=registration; self.roles=roles
        self.git,self.relay,self.bridge=git,relay,bridge
        need(all(p.ledger is registration.ledger and p.t == registration.t
                 for p in (git,relay,bridge)) and bridge.owner is registration.owner
             and relay.relay.budget is registration.ledger,
             'WHOLE_TEAM_SAME_ORIGINAL_TRAJECTORY_PORTS')
        self.gitea_database=NativeWholeTeamPhysicalBackup(registration,
            component='gitea_database',service_names=('gitea',))
        self.collaboration=NativeWholeTeamPhysicalBackup(registration,
            component='collaboration',service_names=('mattermost',*registration.backends))
        self.graph={name:copy.deepcopy(port.graph_domain) for name,port in
            (('gitea',git),('gitea_database',self.gitea_database),
             ('collaboration',self.collaboration),('relay_continuation',relay),('bridge',bridge))}
        from native_service_cut import validate_graph
        self.graph_sha=digest(self.graph);validate_graph(self.graph,self.graph_sha)
    def __call__(self, cut, destination):
        self.registration.frozen(cut.writer_fence)
        need(cut.graph == self.graph and cut.graph_sha == self.graph_sha,
             'WHOLE_TEAM_ORIGINAL_FULL_GRAPH')
        dest=Path(destination)
        git=self.git.run(cut,dest/'git')
        self.gitea_database.run(cut,dest/'gitea-physical')
        self.collaboration.run(cut,dest/'collaboration-physical')
        self.relay.run(cut,dest/'relay',roles=self.roles)
        self.bridge.run(cut,dest/'bridge',git_exports=git['git_exports'])
        self.registration.frozen(cut.writer_fence)
        return {'git_exports':git['git_exports']}
