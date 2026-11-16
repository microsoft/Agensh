"""Original live relay -> real SQLite backups -> exact same-cut service ACK.

This is the relay_continuation producer only, not Gitea/MM async quiescence,
bridge/candidate production, native tool termination or a cold launcher. One
original HTTP/ScientificRelay/PrivateStates instance serves ALL and ONLY this
trajectory. Payloads stay opaque/private; management receipts contain pins and
counts. No database hot-copy, client GET replay, model call or process signal.
"""
from pathlib import Path
import copy,json,os,sqlite3,stat,threading
from common import need,digest,hash_file,private_dir,publish,wire,sync_dir,Refused
from bridge import process_identity
from scientific_relay import ScientificRelay,PrivateStates
from native_scientific_http import NativeScientificHttpServer
from native_service_cut import NativeServiceCut
from native_writer_fence import NativeWriterFence

COMPONENT='relay_continuation'
OBJECTS=frozenset(('relay_continuation','usage_journal'))


def backup_protocol():
    root=Path(__file__).resolve().parent
    return {'schema':'agensh-original-relay-consistent-backup-protocol-v1',
            'implementations':{n:hash_file(root/n)['sha256']for n in
                ('native_relay_backup.py','scientific_relay.py','native_scientific_http.py','budget.py','native_service_cut.py')},
            'sqlite_version':sqlite3.sqlite_version,
            'method':'original-PrivateStates.backup-and-Ledger.backup-native-SQLite-backup-API',
            'objects':sorted(OBJECTS),'scope':'dedicated-original-HTTP-relay-all-and-only-one-trajectory',
            'requires':'model-accounting-and-original-HTTP-delivery-drain-and-all-role-writer-fence;unmanaged-tools-have-no-custody-drain',
            'replay':'none-after-durable-cut-intent','source_mutations':False,
            'not_claimed':['application-Gitea-MM-async-drain','bridge-backup','full-scientific-launch']}


class NativeRelayContinuationBackup:
    def __init__(self,relay,http_server,trajectory):
        need(type(relay)is ScientificRelay and type(http_server)is NativeScientificHttpServer,
             'RELAY_BACKUP_ORIGINAL_RUNTIME_OBJECTS')
        self.relay,self.http,self.ledger,self.t=relay,http_server,relay.budget,trajectory
        self.states=relay.continuations;self.db=self.states.db;self.lock=threading.RLock()
        need(type(self.states)is PrivateStates and relay.states is self.states
             and relay.ledger.states is self.states and http_server.engine is relay
             and http_server.ledger is self.ledger and relay.ledger.admission_gate is http_server.gate,
             'RELAY_BACKUP_ORIGINAL_SHARED_BINDINGS')
        # Share the original Ledger mutex for the full execute/fetchone pair;
        # other trajectories/AUX can already use the same SQLite connection.
        with self.ledger.mutex:
            f=self.ledger.frontier(trajectory);self.roles=tuple(f['roles'])
            need(f['state']=='RUNNING'and f['generation']==1
                 and self.ledger.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(trajectory,)).fetchone()[0]==0,
                 'RELAY_BACKUP_FIRST_START_BEFORE_MODEL')
        need(http_server.registered=={(trajectory,r)for r in self.roles},'RELAY_BACKUP_DEDICATED_TRAJECTORY_HTTP')
        self.home=private_dir(relay.private_home);self.path=self.home/'continuations.sqlite'
        self.owner=process_identity(os.getpid());self.http_pin=http_server.listener_identity_sha256
        self.source=self._source_identity();self.protocol=backup_protocol();self.protocol_sha=digest(self.protocol)
        self.binding={'schema':'agensh-original-relay-backup-binding-v1','trajectory':trajectory,
            'roles':list(self.roles),'owner':self.owner,'http_listener_sha256':self.http_pin,
            'continuation_database_identity':self.source}
        self.instance_sha=digest(self.binding);self.graph_domain={'instance_sha256':self.instance_sha,
            'backup_protocol_sha256':self.protocol_sha,'objects':sorted(OBJECTS)}
        self._runtime()

    def _source_identity(self):
        home=private_dir(self.home);s=self.path.lstat();p=home.stat()
        need(not self.path.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()
             and stat.S_IMODE(s.st_mode)==0o600,'RELAY_BACKUP_ORIGINAL_PRIVATE_DATABASE')
        with self.states.lock:
            files=self.db.execute('PRAGMA database_list').fetchall()
        need([(r[1],r[2])for r in files]==[('main',str(self.path))], 'RELAY_BACKUP_ORIGINAL_OPEN_DATABASE_PATH')
        return {'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'mode':stat.S_IMODE(s.st_mode),
                'home_device':p.st_dev,'home_inode':p.st_ino}

    def _runtime(self):
        self.http.current()
        need(process_identity(os.getpid())==self.owner and self.relay.budget is self.ledger
             and self.relay.continuations is self.states and self.relay.states is self.states
             and self.states.db is self.db and self.relay.ledger.states is self.states
             and self.http.engine is self.relay and self.http.ledger is self.ledger
             and self.relay.ledger.admission_gate is self.http.gate
             and self.http.listener_identity_sha256==self.http_pin
             and self.http.registered=={(self.t,r)for r in self.roles},
             'RELAY_BACKUP_ORIGINAL_RUNTIME_CHANGED')
        need(self._source_identity()==self.source and backup_protocol()==self.protocol
             and digest(self.binding)==self.instance_sha,'RELAY_BACKUP_FROZEN_INPUT_CHANGED')

    def _current(self,cut,roles):
        self._runtime()
        need(type(cut)is NativeServiceCut and cut.ledger is self.ledger and cut.t==self.t,
             'RELAY_BACKUP_ORIGINAL_SERVICE_CUT')
        cut.current({'DRAINING'})
        need(cut.graph[COMPONENT]==self.graph_domain,'RELAY_BACKUP_EXACT_GRAPH_BINDING')
        need(type(cut.writer_fence)is NativeWriterFence,'RELAY_BACKUP_ORIGINAL_WRITER_FENCE_REQUIRED')
        frozen=cut.writer_fence.verify_capture(cut,roles)
        http=self.http.trajectory_park_ready(self.t)
        need(http['safe_to_park_writers']is True and not self.http.lifecycle_storage_unknown,
             'RELAY_BACKUP_ORIGINAL_HTTP_DELIVERY_NOT_DRAINED')
        return frozen,http

    def _private_scope(self,generation):
        # Only ownership metadata/counts are selected. SQL payload columns are
        # never returned to management, printed, or interpreted as model text.
        marks=','.join('?'for _ in self.roles)
        with self.states.lock:
            for table,column in (('states','body'),('parked','identity')):
                need(self.db.execute(f'SELECT COUNT(*)FROM {table} WHERE NOT json_valid({column})').fetchone()[0]==0,
                     'RELAY_BACKUP_PRIVATE_IDENTITY_JSON')
            condition="json_type(body,'$.identity')='array' AND json_array_length(body,'$.identity')=2 AND json_type(body,'$.identity[0]')='text' AND json_type(body,'$.identity[1]')='text' AND json_extract(body,'$.identity[0]')=? AND json_extract(body,'$.identity[1]')IN("+marks+")"
            need(self.db.execute('SELECT COUNT(*)FROM states WHERE COALESCE(('+condition+'),0)=0',(self.t,*self.roles)).fetchone()[0]==0,
                 'RELAY_BACKUP_FOREIGN_CONTINUATION_IDENTITY')
            condition="json_type(identity)='array' AND json_array_length(identity)=2 AND json_type(identity,'$[0]')='text' AND json_type(identity,'$[1]')='text' AND json_extract(identity,'$[0]')=? AND json_extract(identity,'$[1]')IN("+marks+") AND (generation IS NULL OR(typeof(generation)='integer' AND generation>=1 AND generation<=?))"
            need(self.db.execute('SELECT COUNT(*)FROM parked WHERE COALESCE(('+condition+'),0)=0',(self.t,*self.roles,generation)).fetchone()[0]==0,
                 'RELAY_BACKUP_FOREIGN_OR_FUTURE_PARKED_IDENTITY')
            if getattr(self.ledger,'native_unmanaged_cli',False):
                # Explicit native mode has NO tool custody table. Do not query
                # one or recreate an empty legacy table/fake zero receipt.
                need(self.db.execute("SELECT COUNT(*)FROM sqlite_master WHERE name='tools'").fetchone()[0]==0,
                     'RELAY_BACKUP_UNMANAGED_NO_LEGACY_TOOL_STATE')
                tables=('states','parked')
            else:
                need(self.db.execute('SELECT COUNT(*)FROM tools WHERE trajectory<>?OR role NOT IN('+marks+')',(self.t,*self.roles)).fetchone()[0]==0,
                     'RELAY_BACKUP_FOREIGN_TOOL_IDENTITY')
                tables=('states','parked','tools')
            counts={name:self.db.execute('SELECT COUNT(*)FROM '+name).fetchone()[0]for name in tables}
            # Detect writes on this original connection AND another SQLite
            # connection, including payload-only updates with unchanged counts.
            # No payload bytes/values need be selected or hashed for this check.
            version={'connection_total_changes':self.db.total_changes,
                     'data_version':self.db.execute('PRAGMA data_version').fetchone()[0],
                     'schema_version':self.db.execute('PRAGMA schema_version').fetchone()[0]}
        return {'counts':counts,'source_version':version}

    def run(self,cut,destination,*,roles):
        with self.lock:
            frozen,http=self._current(cut,roles)
            with self.ledger.tx():
                rows=self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_RELAY_BACKUP_STARTED'",(self.t,)).fetchall()
                need(not any(json.loads(r[0]).get('cut_sha256')==cut.cut_sha for r in rows),
                     'RELAY_BACKUP_ONE_DURABLE_ATTEMPT_NO_RETRY')
                need(COMPONENT not in cut.receipts,'RELAY_BACKUP_COMPONENT_ALREADY_ACKED')
                self.ledger.event(self.t,'NATIVE_RELAY_BACKUP_STARTED',{'cut_sha256':cut.cut_sha,
                    'instance_sha256':self.instance_sha,'backup_protocol_sha256':self.protocol_sha})
            try:
                dest=Path(destination);need(not dest.exists()and not dest.is_symlink(),'RELAY_BACKUP_NEW_DESTINATION')
                dest=private_dir(dest,create=True);sources={}
                for name in sorted(OBJECTS):sources[name]=private_dir(dest/name,create=True)
                source_scope=self._private_scope(cut.cut['generation']);self._current(cut,roles)
                state_pin=self.states.backup(sources['relay_continuation']/'continuations.sqlite')
                self._current(cut,roles)
                self.ledger.backup(sources['usage_journal']/'usage.sqlite')
                usage_pin=hash_file(sources['usage_journal']/'usage.sqlite')
                self._current(cut,roles)
                need(self._private_scope(cut.cut['generation'])==source_scope,'RELAY_BACKUP_SOURCE_SCOPE_CHANGED')
                receipt={'schema':'agensh-original-relay-consistent-backup-receipt-v1',
                    'cut_sha256':cut.cut_sha,'instance_sha256':self.instance_sha,
                    'backup_protocol_sha256':self.protocol_sha,'http_listener_sha256':self.http_pin,
                    'writer_fence_receipt':frozen,'http_park_counts':http,'private_row_counts':source_scope['counts'],
                    'source_readonly_version':source_scope['source_version'],
                    'outputs':{'continuations.sqlite':state_pin,'usage.sqlite':usage_pin},
                    'source_database_mutated':False,'original_pending_requests_replayed':False,
                    'other_service_async_quiescence_claimed':False}
                publish(dest/'RECEIPT.json',wire(receipt));sync_dir(dest)
                native_ref=cut.cas.store_bytes(wire(receipt));self._current(cut,roles)
                evidence={'cut_sha256':cut.cut_sha,'instance_sha256':self.instance_sha,
                    'backup_protocol_sha256':self.protocol_sha,'receipt_sha256':native_ref['sha256']}
                ref=cut.record_native_backup(COMPONENT,sources,evidence)
                return {'native_receipt':native_ref,'service_receipt':ref,'sources':sources,'destination':dest}
            except BaseException as exc:
                self.ledger.latch_fault(self.t,'NATIVE_RELAY_BACKUP_INCOMPLETE_NO_RETRY')
                try:
                    with self.ledger.tx():self.ledger.event(self.t,'NATIVE_RELAY_BACKUP_FAILED',
                        {'cut_sha256':cut.cut_sha,'exception_type':type(exc).__name__,
                         'code':'NATIVE_RELAY_BACKUP_INCOMPLETE_NO_RETRY'})
                except BaseException:pass
                raise Refused('NATIVE_RELAY_BACKUP_INCOMPLETE_NO_RETRY')from None
