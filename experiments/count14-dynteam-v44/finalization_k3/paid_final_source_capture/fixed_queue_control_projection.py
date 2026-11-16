"""Finite RO metadata adapter: original row-selection, never result/body reads.

Only three exact pinned original wildcard statements are projected. Missing
result is intentional control-view schema, NOT NULL or a fabricated result.
Unknown SQL/wildcards are refused. Original runtime SQL/methods stay untouched.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import importlib
import sqlite3

from common import need
from bounded_metadata_ro import readonly
from queue_control import AUTH, JOBS

PINS = dict(final_queue='7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c',
    final_attempts='9bc1cc86ceb8ae8d017dd0703d1f74cdca356d94882edb15bc600b604686b684',
    queue_control='a3b01a4712d958048d58ab8c9c3ebd1e78b7143728ac0d9686532fdd4d80d382')
BASE = ('id','point','replicate','state','claim','child','terminal')
POINT = ('trajectory','setting','target','input_root','input_policy')
BASE_OLD = ('SELECT jobs.*,points.trajectory,points.setting,points.target,points.input_root,points.input_policy '
    'FROM jobs JOIN points ON jobs.point=points.point WHERE jobs.id=?')


def replacement_old(table):
    return ('SELECT r.*,p.trajectory,p.setting,p.target,p.input_root,p.input_policy FROM '+table+
            ' r JOIN points p ON r.point=p.point WHERE r.id=?')


REWRITES = {BASE_OLD: 'SELECT '+','.join('jobs.'+k for k in BASE)+','+
    ','.join('points.'+k for k in POINT)+' FROM jobs JOIN points ON jobs.point=points.point WHERE jobs.id=?'}
for _table in ('replacement_jobs', JOBS):
    REWRITES[replacement_old(_table)] = ('SELECT '+','.join('r.'+k for k in (*BASE,'attempt','original_job'))+
        ','+','.join('p.'+k for k in POINT)+' FROM '+_table+' r JOIN points p ON r.point=p.point WHERE r.id=?')

FIXED = {
    'SELECT id FROM jobs ORDER BY rowid',
    'SELECT id FROM replacement_jobs ORDER BY rowid',
    'SELECT id FROM '+JOBS+' ORDER BY rowid',
    'SELECT job_id FROM replicate_partials',
    "SELECT name FROM sqlite_master WHERE type='table'",
    'SELECT 1 FROM '+JOBS+' WHERE id=?',
    'SELECT 1 FROM jobs WHERE id=?',
    'SELECT metadata,sha256 FROM '+AUTH+' WHERE id=?',
    'SELECT COUNT(*) FROM '+AUTH,
    'SELECT job_id,metadata FROM replicate_partials ORDER BY job_id',
    'SELECT point,trajectory,setting,target,input_root,input_policy FROM points ORDER BY point',
}
FIXED.update('PRAGMA table_info("'+name+'")' for name in
    ('config','points','jobs','events','replacement_jobs','replicate_partials',AUTH,JOBS))


def verify_sources():
    for name,pin in PINS.items():
        path=Path(importlib.import_module(name).__file__)
        need(path.resolve()==path and not path.is_symlink()
             and hashlib.sha256(path.read_bytes()).hexdigest()==pin,
             'FINAL_CONTROL_PROJECTION_EXACT_ORIGINAL_QUERY_SOURCE_PINS')
    return dict(PINS)


def deny_result_and_event_body(action,table,column,database,origin):
    if action==sqlite3.SQLITE_READ and ((table in ('jobs','replacement_jobs',JOBS) and column=='result')
            or (table=='events' and column=='metadata')):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class FixedControlProjection:
    def __init__(self,bounded):self._bounded=bounded
    def execute(self,sql,parameters=()):
        need(type(sql) is str and (sql in REWRITES or sql in FIXED),
             'FINAL_CONTROL_PROJECTION_UNKNOWN_SQL_OR_WILDCARD_REFUSED')
        return self._bounded.execute(REWRITES.get(sql,sql),parameters)


@contextmanager
def projected_readonly(path,read_budget,unlocked):
    unlocked();read_budget.check();verify_sources()
    with readonly(path,read_budget,unlocked) as bounded:
        # This is a new private mode=ro connection, NEVER a live owner DB.
        bounded.db.set_authorizer(deny_result_and_event_body)
        yield FixedControlProjection(bounded)
        read_budget.check();unlocked()
