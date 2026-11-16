"""Finite private RO metadata views: NO live connection configuration/SQL lock.

Original financial_controls, Ledger.frontier/account and journal_controls code
execute unchanged against the SAME canonical/inode databases via independent
mode=ro/cache=private/timeout=0 connections. These short-lived views are not
scientific objects/owners or authority; no constructor or runtime API is used.
Only local connection VM progress handlers are set. No PRAGMA/BEGIN/COMMIT/
ROLLBACK/interrupt/handler/config change is applied to any live connection.
"""
from contextlib import contextmanager,ExitStack
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib
import os
import sqlite3
import stat
import threading
import time

import normal_cold_sealer as S

PINS=dict(normal_cold_sealer='dd33e7a7a336c872086b3769f70e112942a466a18f52d099ce188ebe1e129e68',
    budget='a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
    final_queue='7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c',
    queue_control='a3b01a4712d958048d58ab8c9c3ebd1e78b7143728ac0d9686532fdd4d80d382',
    anonymous_roster_journal='853a333ead7beb01229412f96d00a1947803b8ad3e8f5599ce93b5d2d02652e4')


def wait(code):raise S.ObservationNotStable(code)


def verify_sources():
    for name,pin in PINS.items():
        p=Path(importlib.import_module(name).__file__)
        S.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
            hashlib.sha256(p.read_bytes()).hexdigest()==pin,'BOUNDED_RO_ORIGINAL_FIXED_METADATA_SOURCE_PINS')
    return dict(PINS)


class ReadBudget:
    def __init__(self,seconds=25):
        S.need(type(seconds)in(int,float)and 0<seconds<=25,'BOUNDED_RO_FINITE_LOCAL_BUDGET')
        self.deadline=time.monotonic()+seconds
    def check(self):
        if time.monotonic()>=self.deadline:wait('NORMAL_SEALER_METADATA_VM_OR_READ_DEADLINE')
    def remaining(self):
        self.check();return max(0,self.deadline-time.monotonic())
    def progress(self):return int(time.monotonic()>=self.deadline)


def token(path,budget):
    budget.check();p=Path(path);s=p.lstat()
    S.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and
        s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1,
        'BOUNDED_RO_SAME_OWNED_PRIVATE_METADATA_DATABASE')
    budget.check();return(s.st_dev,s.st_ino,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))


@contextmanager
def ram_lock(lock,budget):
    budget.check()
    if not lock.acquire(timeout=min(.2,budget.remaining())):wait('NORMAL_SEALER_RAM_CONTROL_LOCK_DEADLINE')
    try:yield
    finally:lock.release()
    budget.check()


class BoundedCursor:
    def __init__(self,cursor,budget,unlocked):self.cursor,self.budget,self.unlocked=cursor,budget,unlocked
    def check(self):self.budget.check();self.unlocked()
    def fetchone(self):
        self.check()
        try:row=self.cursor.fetchone()
        except sqlite3.Error:wait('NORMAL_SEALER_PRIVATE_RO_SQL_WAIT')
        self.check();return row
    def __iter__(self):
        while True:
            row=self.fetchone()
            if row is None:return
            yield row
    def fetchall(self):return list(self)


class BoundedConnection:
    def __init__(self,db,budget,unlocked):self.db,self.budget,self.unlocked=db,budget,unlocked
    def execute(self,sql,parameters=()):
        self.budget.check();self.unlocked()
        S.need(type(sql)is str and(sql.startswith('SELECT ')or sql.startswith('PRAGMA table_info(')),
            'BOUNDED_RO_FIXED_ORIGINAL_SELECT_AND_SCHEMA_ONLY')
        try:cursor=self.db.execute(sql,parameters)
        except sqlite3.Error:wait('NORMAL_SEALER_PRIVATE_RO_SQL_WAIT')
        self.budget.check();self.unlocked()
        return BoundedCursor(cursor,self.budget,self.unlocked)


@contextmanager
def readonly(path,budget,unlocked):
    p=Path(path);before=token(p,budget);unlocked();db=None
    try:
        # New local connection only. Busy waits disabled; long VM scans are
        # interrupted by this connection's own finite progress handler.
        db=sqlite3.connect(p.as_uri()+'?mode=ro&cache=private',uri=True,timeout=0,
            isolation_level=None,check_same_thread=True)
        db.row_factory=sqlite3.Row;db.set_progress_handler(budget.progress,1000)
        S.need(token(p,budget)==before,'BOUNDED_RO_OPEN_SAME_CANONICAL_DATABASE_INODE')
        yield BoundedConnection(db,budget,unlocked)
        S.need(token(p,budget)==before,'BOUNDED_RO_DATABASE_IDENTITY_UNCHANGED_AFTER_READ')
    except sqlite3.Error:
        wait('NORMAL_SEALER_PRIVATE_RO_OPEN_OR_READ_WAIT')
    finally:
        if db is not None:db.close() # normal close of OWN RO connection only


def financial_controls(core,approved,budget):
    from budget import Ledger
    from final_queue import FinalQueue
    from queue_control import CarrierQueueDomain
    verify_sources();budget.check()
    l,q=core.ledger,core.queue
    S.need(type(l)is Ledger and type(q)is FinalQueue and type(approved)is CarrierQueueDomain and approved.q is q,
        'BOUNDED_RO_EXACT_REGISTERED_ORIGINAL_FINANCE_COMPONENTS')
    def unlocked():
        S.need(not l.mutex._is_owned()and not q.mutex._is_owned(),
            'BOUNDED_RO_NEVER_SQL_WHILE_HOLDING_LIVE_SCIENCE_OR_QUEUE_LOCK')
    unlocked()
    with ram_lock(l.mutex,budget):
        roles=SimpleNamespace(epoch=core.roles.epoch,births=dict(core.roles.births),held=set(core.roles.held))
    with ExitStack()as stack:
        ld=stack.enter_context(readonly(l.home/'ledger.sqlite',budget,unlocked))
        qd=stack.enter_context(readonly(q.home/'queue.sqlite',budget,unlocked))
        lv=Ledger.__new__(Ledger);lv.home,lv.db,lv.mutex=l.home,ld,threading.RLock()
        qv=FinalQueue.__new__(FinalQueue);qv.home,qv.db,qv.mutex=q.home,qd,threading.RLock()
        av=CarrierQueueDomain.__new__(CarrierQueueDomain);av.q=qv
        view=SimpleNamespace(ledger=lv,queue=qv,roles=roles,rows=core.rows,metadata_RO_view_only=True)
        S.need(lv.frontier.__func__ is Ledger.frontier and lv.account.__func__ is Ledger.account and
            lv.mutex is not l.mutex and qv.mutex is not q.mutex,
            'BOUNDED_RO_ORIGINAL_FRONTIER_ACCOUNT_CODE_NO_STUB_OR_FALLBACK')
        result=S.financial_controls(view,av) # EXACT original code/formulas/queries
        budget.check();unlocked();return result


def projection_view(projection,budget):
    names=('block','arm','observation_basis','complete_history','roles','_live','_seen',
           '_births','_worker_births','_sessions','_sequence','_previous','_anchor')
    with ram_lock(projection._lock,budget):
        fields=copy.deepcopy({name:getattr(projection,name)for name in names})
    # Original anonymous snapshot code consumes this detached control-only RAM
    # view; never a scientific projection or journal authority.
    return SimpleNamespace(_lock=threading.Lock(),**fields)


def journal_controls(core,budget):
    from anonymous_roster_journal import AnonymousRosterJournal
    verify_sources();budget.check();journals={}
    def unlocked():
        S.need(not core.ledger.mutex._is_owned(),
            'BOUNDED_RO_JOURNAL_SQL_OUTSIDE_LIVE_SCIENCE_LOCK')
    unlocked()
    with ExitStack()as stack:
        for t,original in sorted(core.journals.items()):
            budget.check()
            S.need(type(original)is AnonymousRosterJournal,'BOUNDED_RO_ORIGINAL_ANONYMOUS_JOURNAL_TYPE')
            view=AnonymousRosterJournal.__new__(AnonymousRosterJournal)
            view.path,view.qualification_only=original.path,original.qualification_only
            view.projection=projection_view(original.projection,budget)
            view.db=stack.enter_context(readonly(original.path,budget,unlocked))
            journals[t]=view
        result=S.journal_controls(SimpleNamespace(journals=journals,rows=core.rows))
        budget.check();unlocked();return result
