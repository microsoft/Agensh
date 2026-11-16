"""Exclusive existing-DB attachment, deliberately READ ONLY in this first layer.

Reuses seed46_disk_attach._open's existing private lock/inode + after-flock old
owner recheck pattern. No original Ledger/FinalQueue constructor, migration,
owner marker edit, SENT/permit/job reclassification, financial/event write.
"""
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
import copy
import fcntl
import hashlib
import os
import sqlite3
import threading

from paid_cold_material import PaidColdWait, digest, existing, need, verify_ended, wire


def sqlite_state_pin(db):
    """All tables/schema, including approved carrier extensions; hashes only.

    Values are control SQLite metadata, never request bodies read from SDKs or
    scientific filesystem trees. BLOBs remain opaque. No tables are omitted.
    """
    def value(v):
        if type(v) is bytes:
            return dict(opaque_blob_sha256=hashlib.sha256(v).hexdigest(), bytes=len(v))
        return v
    schema = [tuple(r) for r in db.execute(
        'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')]
    tables = {}
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        rows = [[value(v) for v in tuple(r)] for r in db.execute('SELECT * FROM ' + quoted)]
        tables[name] = dict(rows=len(rows), sha256=digest(sorted(rows, key=wire)))
    return dict(schema_sha256=digest(schema), tables=tables, state_sha256=digest([schema, tables]))


@dataclass(frozen=True)
class RetainedUnboundNativeCustody:
    original_control: dict
    native_handle_bound: bool = False


def refuse_runtime(*args, **kwargs):
    raise PaidColdWait('PAID_COLD_TYPED_CUSTODY_ONLY_RUNTIME_NOT_HYDRATED')


def quarantine_methods(instance, cls):
    """Instance-only; original types/classes/code objects are never changed."""
    for name in vars(cls):
        if not name.startswith('__') and callable(getattr(cls, name, None)):
            setattr(instance, name, MethodType(refuse_runtime, instance))


class AttachedPair:
    """Retained exact classes/connections/real flock FDs, no launch capability."""
    def __init__(self):
        self.lock_fds = []
        self.connections = []
        self.ledger = self.queue = None
        self.control_locks = ()

    def release_failed_pre_runtime_attach(self):
        # No original close(): that may unlink owner.open or alter clean state.
        # This is not a native-child teardown and never removes control files.
        for db in self.connections:
            db.close()
        self.connections.clear()
        for fd in self.lock_fds:
            os.close(fd)
        self.lock_fds.clear()


def attach_existing_pair(handoff, scope, control, current_birth):
    from budget import Ledger
    from final_queue import FinalQueue
    pair = AttachedPair()
    verify_ended(handoff, current_birth)
    owner_home = existing(handoff['owner_home'], directory=True, private=True)
    ledger_home = existing(handoff['ledger']['home'], directory=True, private=True)
    queue_home = existing(handoff['queue']['home'], directory=True, private=True)
    need(ledger_home == owner_home/'ledger' and queue_home == owner_home/'final-queue',
         'PAID_COLD_EXACT_EXISTING_LEDGER_AND_QUEUE_HOMES')
    lock_rows = list(handoff['control_locks']) + [handoff['ledger']['lock'], handoff['queue']['lock']]
    paths = [existing(row, private=True) for row in lock_rows]
    need(len(paths) == len(set(paths)) and paths[-2:] == [ledger_home/'owner.lock', queue_home/'owner.lock'] and
         all(p.is_relative_to(owner_home) for p in paths), 'PAID_COLD_EXACT_EXISTING_LOCK_INVENTORY')
    try:
        log_row = control['full_used_log_directory']
        log_path = existing(log_row, directory=True, private=True)
        need(log_path == owner_home/'full-affinity-domain-control-v1', 'PAID_COLD_ORIGINAL_DOMAIN_DIRECTORY_LOCK')
        fd = os.open(log_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        pair.lock_fds.append(fd)
        need((os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (log_row['device'], log_row['inode']),
             'PAID_COLD_ORIGINAL_DOMAIN_DIRECTORY_LOCK_INODE')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_ended(handoff, current_birth)
        for row, path in zip(lock_rows, paths):
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            pair.lock_fds.append(fd)
            need((os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (row['device'], row['inode']),
                 'PAID_COLD_OPENED_ORIGINAL_LOCK_INODE')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            verify_ended(handoff, current_birth)
        pair.control_locks = tuple(paths)
        for which, home, filename in (('ledger', ledger_home, 'ledger.sqlite'), ('queue', queue_home, 'queue.sqlite')):
            path = existing(handoff[which]['database'], private=True)
            need(path == home/filename, 'PAID_COLD_ORIGINAL_DATABASE_FILENAME')
            # Deliberately stronger than seed46's rw stage: no write path exists
            # until a separately reviewed complete runtime hydrator is supplied.
            db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, isolation_level=None,
                                 check_same_thread=False, timeout=1)
            pair.connections.append(db)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA query_only=ON')
            existing(handoff[which]['database'], private=True)
            need(sqlite_state_pin(db) == handoff[which]['state_pin'],
                 'PAID_COLD_ALL_ORIGINAL_TABLES_SCHEMA_AND_ROWS_PIN')
        verify_ended(handoff, current_birth)
        ledger_db, queue_db = pair.connections
        accounts = {r['trajectory']: dict(r) for r in ledger_db.execute('SELECT * FROM accounts')}
        need(set(accounts) == set(scope.rows) and
             all(r['manifest_sha'] == scope.canonical_sha256 for r in accounts.values()) and
             sum(r['actual'] for r in accounts.values()) > 0 and
             ledger_db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] > 0,
             'PAID_COLD_EXISTING_PAID_SCOPE_NOT_ZERO_INITIALIZATION')
        import json
        need(all(json.loads(accounts[t]['roles']) == row['roles'] for t, row in scope.rows.items()),
             'PAID_COLD_ORIGINAL_LEDGER_CATALOGUES')
        config = queue_db.execute('SELECT manifest,cap FROM config WHERE singleton=1').fetchone()
        need(config is not None and config['manifest'] == scope.canonical_sha256 and
             type(config['cap']) is int and 1 <= config['cap'] <= 12,
             'PAID_COLD_ORIGINAL_QUEUE_MANIFEST_AND_CAP')
        memory = control['ledger_memory']
        need(type(memory) is dict and set(memory) == {'memory_faults', 'native_custody', 'native_unmanaged_cli'} and
             memory['native_unmanaged_cli'] is True and type(memory['memory_faults']) is dict and
             type(memory['native_custody']) is dict and
             all(t in scope.rows and type(v) is str and v for t, v in memory['memory_faults'].items()),
             'PAID_COLD_SEALED_FAULT_AND_NATIVE_CUSTODY_REQUIRED_NEVER_DEFAULT_EMPTY')
        marker = existing(control['owner_marker'], private=True)
        need(marker == ledger_home/'owner.open', 'PAID_COLD_ORIGINAL_OWNER_MARKER_RETAINED')
        ledger = Ledger.__new__(Ledger)
        ledger.home, ledger.fd, ledger.db = ledger_home, pair.lock_fds[-2], ledger_db
        ledger.mutex = threading.RLock()
        ledger.capacity_changed = threading.Condition(ledger.mutex)
        ledger.memory_faults = copy.deepcopy(memory['memory_faults'])
        ledger.native_services = {s: RetainedUnboundNativeCustody(copy.deepcopy(v))
                                  for s, v in memory['native_custody'].items()}
        ledger.native_unmanaged_cli, ledger.owner_marker = True, marker
        ledger._dynteam_catalogues = {t: tuple(row['roles']) for t, row in scope.rows.items()}
        ledger._dynteam_qualification_only = scope.qualification_only
        queue = FinalQueue.__new__(FinalQueue)
        queue.home, queue.fd, queue.db = queue_home, pair.lock_fds[-1], queue_db
        queue.manifest, queue.cap, queue.mutex = config['manifest'], config['cap'], threading.RLock()
        pair.ledger, pair.queue = ledger, queue
        # No default old-table carrier reader or mutable original API may be
        # mistaken for fully restored authority while extension hydration waits.
        quarantine_methods(ledger, Ledger)
        quarantine_methods(queue, FinalQueue)
        need(sqlite_state_pin(ledger_db) == handoff['ledger']['state_pin'] and
             sqlite_state_pin(queue_db) == handoff['queue']['state_pin'],
             'PAID_COLD_ATTACH_NO_RECLASSIFICATION_OR_LEDGER_QUEUE_WRITE')
        return pair, accounts
    except BaseException:
        pair.release_failed_pre_runtime_attach()
        raise
