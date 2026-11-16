"""Bounded resource-source projections, not an admission proof or dispatcher.

Only fixed PUBLIC control fields, native financial COUNTs, original health
aggregates, kernel/mount identity and exact private Docker image IDs are read.
No target/candidate/pickle/message/log/credential body is inspected. These
functions must run in a finite read-only sampler child, outside science locks;
the SAME-owner producer/publication supervisor is still a separate binding.
"""
from pathlib import Path
from types import ModuleType,SimpleNamespace
import ast
import contextlib
import hashlib
import json
import os
import socket
import sqlite3
import stat
import struct
import subprocess
import time
import math
from urllib.parse import urlsplit

from common import need
from native_peer_registry import ProcessBirth,process_birth
from native_docker_scope import ScopedDocker,sha64

PINS={'own_resource_observer.py':'b911797ce00f8256b934f1980858a4c9c3b97e681915e9678442d172ee8c6a74',
      'selected_numeric.py':'dc136c2df6e39d27b4ccb5b0c770675e85d523013933f97962a0005f7c2891f2',
      'performance_patch.py':'3f55fbcdfb0d2beb13e56010a730151e786b61fec7e0c042358a506f1d255888',
      'aggregate_patch.py':'63f5d778b23df374e2cf3b4f9d328a01f5ed352b33dfd457a8ac9fcbbd84de27',
      'rejection_slots.py':'a4713627652ce64027000adb6002177c8bc7379e69dc74081e71d0a141c6a47f',
      'publisher_only.py':'6bbdda94209bdbf4a5ffee04e962d7240625a7fdb9fda5bca3df4dea16860386'}
IMAGE='{"id":{{json .Id}},"digests":{{json .RepoDigests}},"layers":{{json .RootFS.Layers}}}'


def frozen_observer():
    """Private import instances; never replace any live/global old observer.

    Only the original import of selected_numeric is replaced with the exact
    privately loaded, byte-pinned class. No original predicate/SQL is changed.
    Default old deployment entrypoints are NOT called by this library.
    """
    root=Path(__file__).resolve().parents[1]/'original-v2-resource-observer-v1'
    modules={}
    for name in ('selected_numeric.py','own_resource_observer.py','performance_patch.py',
                 'aggregate_patch.py','rejection_slots.py','publisher_only.py'):
        path=root/name;raw=path.read_bytes()
        need(path.resolve()==path and not path.is_symlink() and hashlib.sha256(raw).hexdigest()==PINS[name],
             'DYNTEAM_ORIGINAL_RESOURCE_SOURCE_PIN')
        tree=ast.parse(raw);module=ModuleType('count14_private_'+path.stem)
        module.__file__=str(path)
        if name=='own_resource_observer.py':
            sites=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=='selected_numeric']
            need(len(sites)==1 and len(sites[0].names)==1 and sites[0].names[0].name=='SelectedJSON',
                 'DYNTEAM_ONE_ORIGINAL_OBSERVER_DEPENDENCY_BINDING')
            tree.body.remove(sites[0]);module.SelectedJSON=modules['selected_numeric.py'].SelectedJSON
        exec(compile(ast.fix_missing_locations(tree),str(path),'exec'),module.__dict__)
        modules[name]=module
    observer=modules['own_resource_observer.py']
    modules['aggregate_patch.py'].install(observer)
    modules['rejection_slots.py'].install(observer,(root/'own_resource_observer.py').read_text())
    return observer,modules['performance_patch.py']


def _readonly(path):
    path=Path(path)
    need(path.is_absolute() and path.resolve()==path and not path.is_symlink() and
         path.name=='ledger.sqlite' and path.parent.name=='ledger' and path.parent.parent.name=='owner' and
         stat.S_ISREG(path.lstat().st_mode),'DYNTEAM_RESOURCE_EXACT_REGISTERED_NATIVE_LEDGER')
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.2)
    try:
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA busy_timeout=200')
        deadline=time.monotonic()+3
        db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
        db.execute('BEGIN') # private RO snapshot, never the scientific connection
    except BaseException:db.close();raise
    return db


def native_projection(path,trajectory_roots,*,physical_clause,now_ns=None,observer=None):
    """Actual SAME new Ledger capacity view, not old raw-SENT approximations.

    `physical_clause` must be the frozen original native_v2_dispositions AST
    literal verified by the sampler factory, not caller SQL/receipt contents.
    The SQL exports only counts/trajectory enums. No experiment rows change.
    """
    path=Path(path)
    need(path.name=='ledger.sqlite' and path.parent.name=='ledger' and path.parent.parent.name=='owner',
         'DYNTEAM_RESOURCE_NEW_FINANCIAL_LEDGER_PATH_ONLY_NO_PKL_OR_LOG_READ')
    source=Path(__file__).with_name('native_v2_dispositions.py')
    tree=ast.parse(source.read_bytes())
    literals=[n.value for n in tree.body if isinstance(n,ast.Assign) and
              any(isinstance(t,ast.Name) and t.id=='PHYSICAL_TERMINAL' for t in n.targets)]
    need(len(literals)==1 and physical_clause==ast.literal_eval(literals[0]),
         'DYNTEAM_RESOURCE_ORIGINAL_PHYSICAL_SELECT_LITERAL_ONLY')
    need(type(trajectory_roots) is dict and trajectory_roots and
         len(set(trajectory_roots.values()))==len(trajectory_roots) and
         all(type(k) is str and type(v) is str and Path(v).is_absolute() for k,v in trajectory_roots.items()),
         'DYNTEAM_RESOURCE_COMPLETE_TRAJECTORY_ROOT_ENUM')
    before=Path(path).lstat();now=time.time_ns() if now_ns is None else now_ns
    with contextlib.closing(_readonly(path)) as db:
        need({r[0] for r in db.execute('SELECT trajectory FROM accounts')}==set(trajectory_roots),
             'DYNTEAM_RESOURCE_NO_MISSING_NEW_LEDGER_ACCOUNTS')
        main=dict(db.execute("SELECT trajectory,COUNT(*) FROM upstream_effective_requests WHERE "
             "state IN ('RESERVED','SENT','UNKNOWN') AND "+physical_clause+' GROUP BY trajectory'))
        auxiliary=dict(db.execute("SELECT s.trajectory,COUNT(*) FROM aux_permits p JOIN aux_scopes s ON p.scope=s.scope "
             "WHERE p.state IN ('RESERVED','SENT','UNKNOWN') GROUP BY s.trajectory"))
        # Exact installed ORIGINAL queries, including its validated AUX
        # terminal disambiguation. Never reintroduce the intermediate-POSSIBLE
        # bug by copying an older SQL literal into a new deployment.
        O,_=frozen_observer()
        main_sql=[s for s in O.native.__code__.co_consts if type(s) is str and
                  s.startswith("WITH t AS(SELECT json_extract(metadata,'$.request_id')")]
        aux_sql=[s for s in O.native.__code__.co_consts if type(s) is str and
                 s.startswith("WITH t AS(SELECT json_extract(metadata,'$.permit_id')")]
        need(len(main_sql)==len(aux_sql)==1,'DYNTEAM_EXACT_INSTALLED_ORIGINAL_HEALTH_QUERY_LITERALS')
        calls,bad=db.execute(main_sql[0],(now-600*10**9,now)).fetchone()
        aux_calls,aux_bad=db.execute(aux_sql[0],(now-600*10**9,now)).fetchone()
        first=db.execute("SELECT MAX(at_ns)FROM events WHERE kind='FIRSTSTART'").fetchone()[0]
        need(type(first) is int and first<=now,'DYNTEAM_RESOURCE_ORIGINAL_FIRSTSTART_TIMESTAMP')
    after=Path(path).lstat()
    need((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino) and
         set(main)|set(auxiliary)<=set(trajectory_roots),'DYNTEAM_RESOURCE_STABLE_NEW_LEDGER_IDENTITY')
    rows=[dict(root=root,FP8_inflight=main.get(t,0)+auxiliary.get(t,0)) for t,root in trajectory_roots.items()]
    return dict(roots=rows,total_FP8_inflight=sum(r['FP8_inflight'] for r in rows),
                terminals=calls+aux_calls,errors=bad+aux_bad,observed_ns=now,
                own_window_covered_seconds=min(600,(now-first)/10**9),
                device=after.st_dev,inode=after.st_ino,readonly_financial_tables=True)


def registered_outside_projection(registry_path,registry_sha256,cache_directory,*,contract_sha256,
                                  forbidden_native_ledgers=(),qualification_only=False,OWN_metrics_url=None,
                                  allow_missing_health=False):
    """The ORIGINAL bounded25s reader/index/TTFT over a frozen outside registry.

    Source registries/counts are never rewritten; only the new-root PUBLIC
    health index/window is appended. This is a finite sampler-child operation,
    not a new resident observer. All deployment facts still must be supplied by
    the real original OPS registry; no invented zero/complete/fresh fallback.
    """
    O,P=frozen_observer();path=Path(registry_path);directory=Path(cache_directory)
    need(type(qualification_only) is bool and directory.is_absolute() and directory.resolve()==directory and
         not directory.is_symlink() and sha64(contract_sha256),'DYNTEAM_RESOURCE_OUTSIDE_REGISTRY_BOUND_SCOPE')
    raw,_=O.read(path,2**20);need(hashlib.sha256(raw).hexdigest()==registry_sha256,
                               'DYNTEAM_RESOURCE_FROZEN_OUTSIDE_REGISTRY_SHA')
    value=json.loads(raw)
    need(value.get('dynteam_excludes_new_cohort_contract_sha256')==contract_sha256 and
         value.get('no_active_unregistered_roots') is True,
         'DYNTEAM_OUTSIDE_SCOPE_CANNOT_SILENTLY_INCLUDE_NEW_COHORT')
    paths=[*value['native_ledgers'],*value['scale_reservation_books'],*value['scale_request_roots'],
           *value.get('scale_search_settings',[]),value['system_health'],value['system_root'],value['scale_physical_unknown_root']]
    need(not(set(map(str,forbidden_native_ledgers))&set(value['native_ledgers'])),
         'DYNTEAM_OUTSIDE_CENSUS_CANNOT_DOUBLE_COUNT_OWN_LEDGER')
    if qualification_only:
        need(all(any(x.startswith('OWN-') for x in Path(p).parts) for p in [path,directory,*paths]),
             'DYNTEAM_OUTSIDE_OWN_FIXTURE_NEVER_READS_REAL_SOURCES')
        u=urlsplit(OWN_metrics_url or '')
        need(u.scheme=='http' and u.hostname=='127.0.0.1' and u.port and u.username is None and u.password is None and
             u.path=='/metrics' and not u.query and not u.fragment,'DYNTEAM_OUTSIDE_OWN_METRICS_LOOPBACK_ONLY')
        O.METRICS=OWN_metrics_url
        request=O.urllib.request
        O.urllib=SimpleNamespace(request=SimpleNamespace(Request=request.Request,
            urlopen=request.build_opener(request.ProxyHandler({})).open)) # private OWN module only
        registered=(value,registry_sha256) # ORIGINAL explicitly OWN-only seam
    else:
        need(OWN_metrics_url is None and directory.is_relative_to('/mnt/ptb-scratch2') and
             directory.parts[3].startswith('count14-dynteam'),
             'DYNTEAM_OUTSIDE_HEALTH_INDEX_ONLY_NEW_ROOT_NO_HOST_CONFIG_CHANGE')
        O.BOOT=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        original_inventory=O.inventory
        def exact_inventory():
            v,pin=original_inventory(path)
            need(pin==registry_sha256 and v==value,'DYNTEAM_OUTSIDE_REGISTRY_UNCHANGED_DURING_READ')
            return v,pin
        O.inventory=exact_inventory;registered=None
    collect=P.collect
    if allow_missing_health:
        # ONLY the last TTFT/health-index phase may be unavailable. All root
        # enumeration/physical counts MUST still succeed. This keeps independent
        # SYSTEM admission possible without manufacturing a healthy p95 or0%.
        import copy
        source=ast.parse(Path(P.__file__).read_bytes())
        node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='collect')
        original=copy.deepcopy(node);sites=[]
        for parent in ast.walk(node):
            body=getattr(parent,'body',None)
            if not isinstance(body,list):continue
            for i,n in enumerate(body):
                if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='p95':
                    sites.append((body,i))
        need(len(sites)==1,'DYNTEAM_ONE_ORIGINAL_OUTSIDE_HEALTH_PHASE')
        body,i=sites[0];need(isinstance(body[i+1],ast.Assign) and
            isinstance(body[i+1].targets[0],ast.Name) and body[i+1].targets[0].id=='h',
            'DYNTEAM_ORIGINAL_TTFT_THEN_HEALTH_ONLY')
        pair=body[i:i+2]
        handler=ast.ExceptHandler(type=ast.Name(id='Exception',ctx=ast.Load()),name='failure',body=ast.parse(
            "h=None\nhealth_failure_type=type(failure).__name__").body)
        replacement=ast.parse('health_failure_type=None').body+[ast.Try(body=pair,handlers=[handler],orelse=[],finalbody=[])]
        body[i:i+2]=replacement
        for n in ast.walk(node):
            if isinstance(n,ast.Return):
                b=next(b for b in ast.walk(node) if isinstance(getattr(b,'body',None),list) and n in b.body)
                b.body.insert(b.body.index(n),ast.parse("own['health_unavailable_exception_type']=health_failure_type").body[0]);break
        # Reverse exactly the inserted phase/metadata and compare original AST.
        reverted=copy.deepcopy(node)
        for b in ast.walk(reverted):
            if not isinstance(getattr(b,'body',None),list):continue
            out=[]
            for n in b.body:
                if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='health_failure_type':continue
                if isinstance(n,ast.Try) and len(n.handlers)==1 and n.handlers[0].name=='failure':out.extend(n.body);continue
                if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Subscript) and isinstance(n.targets[0].slice,ast.Constant) and n.targets[0].slice.value=='health_unavailable_exception_type':continue
                out.append(n)
            b.body=out
        need(ast.dump(reverted,include_attributes=False)==ast.dump(original,include_attributes=False),
             'DYNTEAM_OUTSIDE_COUNTS_ORIGINAL_AST_UNCHANGED')
        scope=dict(P.__dict__);exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                                         __file__+':optional_health_only','exec'),scope)
        collect=scope['collect']
    own,health=collect(O,registered=registered,directory=directory,budget=4)
    own['scope']='REGISTERED_PREEXISTING_ROOTS_ONLY'
    own['excludes_new_cohort_contract_sha256']=contract_sha256
    return own,health


def merge_cohort_counts(outside,health,native,system,*,contract_sha256,outside_maximum,now_ns=None):
    """Truthful union of exact disjoint relay roots and SYSTEM controls.

    No host resource booleans or financial effects are manufactured. Health
    warmup/zero-denominator remains undefined; source timestamps are NOT reset.
    The producer must still add actual kernel/daemon/storage evidence before
    publishing a receipt consumed by NativeCohortResources.
    """
    now=time.time_ns() if now_ns is None else now_ns
    need(type(outside_maximum) is int and 0<=outside_maximum<=94 and
         outside.get('schema')=='count14-own-fp8-relay-counts-v1' and
         outside.get('scope')=='REGISTERED_PREEXISTING_ROOTS_ONLY' and
         outside.get('excludes_new_cohort_contract_sha256')==contract_sha256 and
         outside.get('all_count14_roots_included') is True and outside.get('counts_from_relay_ledgers') is True,
         'DYNTEAM_COHORT_COMPLETE_REGISTERED_DISJOINT_OUTSIDE_SCOPE')
    sources=[outside,health,native,system]
    need(all(type(v.get('observed_ns')) is int and 0<=now-v['observed_ns']<=60*10**9 for v in sources),
         'DYNTEAM_COHORT_NO_RESTAMPING_EXPIRED_PROJECTION')
    rows=[dict(r) for r in outside['roots']];own=[dict(r) for r in native['roots']]
    own.append(dict(root=system['root'],FP8_inflight=system['FP8_inflight']))
    allrows=rows+own
    need(all(type(r['FP8_inflight']) is int and r['FP8_inflight']>=0 and type(r['root']) is str and
             Path(r['root']).is_absolute() and str(Path(r['root']))==r['root'] and '..' not in Path(r['root']).parts
             for r in allrows) and
         len({r['root'] for r in allrows})==len(allrows),'DYNTEAM_COHORT_UNIQUE_NUMERIC_ROOTS')
    need(not any(Path(a['root']).is_relative_to(b['root']) or Path(b['root']).is_relative_to(a['root'])
                 for a in rows for b in own),'DYNTEAM_COHORT_ANCESTOR_SOURCE_OVERLAP_REFUSED')
    other=sum(r['FP8_inflight'] for r in rows)
    need(other==outside['total_FP8_inflight'] and 0<=system['FP8_inflight']<=2 and
         sum(r['FP8_inflight'] for r in native['roots'])==native['total_FP8_inflight'],
         'DYNTEAM_COHORT_ACTUAL_RELAY_SUMS_NO_COUNT_FORGIVENESS')
    p95=health['gateway_FP8_TTFT_p95_seconds']
    need(type(p95) in (int,float) and math.isfinite(p95) and p95>=0,
         'DYNTEAM_COHORT_REAL_NUMERIC_TTFT_NOT_ASSUMED_HEALTHY')
    need(health.get('own_window_seconds')==600,'DYNTEAM_COHORT_ORIGINAL_600_SECOND_HEALTH_WINDOW')
    need(health.get('schema')=='count14-own-resource-health-v1' and
         all(type(v[k]) is int and v[k]>=0 for v,keys in
             ((health,('own_requests','own_5xx_or_UNKNOWN_requests')),(native,('terminals','errors')),
              (system,('terminals','errors'))) for k in keys) and
         health['own_5xx_or_UNKNOWN_requests']<=health['own_requests'] and
         native['errors']<=native['terminals'] and system['errors']<=system['terminals'] and
         type(health.get('own_rate_defined')) is bool and health['own_rate_defined'] is
         (health['own_window_covered_seconds']==600 and health['own_requests']>0),
         'DYNTEAM_COHORT_ALL_SOURCE_COUNTS_AND_UNDEFINED_RATES_TRUTHFUL')
    calls=health['own_requests']+native['terminals']+system['terminals']
    bad=health['own_5xx_or_UNKNOWN_requests']+native['errors']+system['errors']
    need(all(type(v) is int and v>=0 for v in (calls,bad)) and bad<=calls,
         'DYNTEAM_COHORT_NUMERIC_HEALTH_TOTALS')
    covered=min(health['own_window_covered_seconds'],native['own_window_covered_seconds'])
    need(type(covered) in (int,float) and 0<=covered<=600,'DYNTEAM_COHORT_TRUTHFUL_CONTINUOUS_COVERAGE')
    observed=min(v['observed_ns'] for v in sources)
    return (dict(schema='count14-own-fp8-relay-counts-v1',observed_ns=observed,all_count14_roots_included=True,
            counts_from_relay_ledgers=True,roots=allrows,total_FP8_inflight=other+native['total_FP8_inflight']+system['FP8_inflight'],
            SAMPLE_NONATOMIC_CONSERVATIVE=True,publish_observation_only_not_admission=True,
            allocation_observation_within_declared_bound=(other<=outside_maximum and
                native['total_FP8_inflight']<=96-2-outside_maximum),
            all_own_FP8_observed_at_most96=sum(r['FP8_inflight'] for r in allrows)<=96),
            dict(schema='count14-own-resource-health-v1',observed_ns=observed,gateway_FP8_TTFT_p95_seconds=p95,
            own_window_seconds=600,own_window_covered_seconds=covered,own_rate_defined=covered==600 and calls>0,
            own_requests=calls,own_5xx_or_UNKNOWN_requests=bad))


def _optional_system_controls(reader,wanted):
    # Original bounded lexical scanner, only its final required-key equality
    # becomes optional. No JSON decode of an unselected value is introduced.
    original=type(reader).select
    path=Path(original.__code__.co_filename)
    need(path.resolve()==path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest()==PINS['selected_numeric.py'],
         'SYSTEM_OPTIONAL_SCALARS_ORIGINAL_BOUNDED_READER_PIN')
    text=path.read_bytes();module=ast.parse(text)
    cls=next(n for n in module.body if isinstance(n,ast.ClassDef)and n.name=='SelectedJSON')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='select')
    expected=compile(text,str(path),'exec',dont_inherit=True,optimize=__import__('sys').flags.optimize)
    def codes(c):
        return [c]+[v for k in c.co_consts if type(k)is type(c)for v in codes(k)]
    need(original.__code__ in codes(expected),'SYSTEM_ORIGINAL_FULL_SELECTED_READER_CODETYPE')
    before=ast.dump(fn,include_attributes=False)
    target=ast.parse('set(out)!=set(wanted)',mode='eval').body
    hits=[]
    class Optional(ast.NodeTransformer):
        def visit_Compare(self,n):
            if ast.dump(n,include_attributes=False)==ast.dump(target,include_attributes=False):
                hits.append(n);return ast.copy_location(ast.Constant(False),n)
            return self.generic_visit(n)
    selected=Optional().visit(fn)
    need(len(hits)==1,'SYSTEM_OPTIONAL_ONLY_FINAL_REQUIRED_KEY_COMPARISON')
    import copy
    class Inverse(ast.NodeTransformer):
        def visit_Constant(self,n):
            if n.value is False:return ast.copy_location(copy.deepcopy(hits[0]),n)
            return n
    need(ast.dump(Inverse().visit(copy.deepcopy(selected)),include_attributes=False)==before,
         'SYSTEM_OPTIONAL_SCANNER_FULL_BODY_INVERSE')
    # The scanner still checks duplicates, depth, lexical syntax, scalar type
    # and bounds. Caller explicitly enforces its required legacy fields.
    ns=dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[selected],type_ignores=[])),
         str(path)+':optional-system-two-scalars','exec'),ns)
    return ns['select'](reader,wanted)


def system_projection(home,*,contract_sha256,now_ns=None,observer=None,registered=True):
    """Only our fixed intent/terminal controls; NOT_STARTED is not a request.

    Missing/unknown HTTP terminals retain a slot even after a child exit. A
    returned closed HTTP error frees physical capacity but never its expense.
    No process existence heuristic, JSON message, key path or response decode.
    """
    O=frozen_observer()[0] if observer is None else observer
    home=Path(home);now=time.time_ns() if now_ns is None else now_ns;occupied=calls=bad=0;seen=set()
    need(home.resolve()==home and not home.is_symlink() and sha64(contract_sha256),
         'DYNTEAM_RESOURCE_SYSTEM_EXACT_PUBLIC_HOME')
    need(type(registered) is bool,'DYNTEAM_SYSTEM_REGISTRATION_BOOLEAN_FROM_SAME_OWNER')
    if not registered:
        need(not home.exists(),'DYNTEAM_SYSTEM_UNREGISTERED_HOME_CANNOT_HAVE_STATE')
        return dict(root=str(home),FP8_inflight=0,terminals=0,errors=0,observed_ns=now)
    need(home.exists() and home.is_dir(),'DYNTEAM_SYSTEM_REGISTERED_HOME_MISSING_IS_NOT_ZERO')
    for directory in sorted(home.glob('????????-count14-dynteam-system-*')):
        O.canonical(directory);need(directory.is_dir(),'DYNTEAM_RESOURCE_SYSTEM_DIRECTORY_ONLY')
        raw,_=O.read(directory/'INTENT_PUBLIC.json');intent=O.SelectedJSON(raw.decode('utf-8','strict')).select(
            {'schema','sequence','contract_sha256'})
        need(intent['schema']=='count14-dynteam-system-probe-intent-v1' and type(intent['sequence']) is int and
             intent['sequence']>0 and intent['contract_sha256']==contract_sha256 and
             intent['sequence'] not in seen and directory.name.startswith(f"{intent['sequence']:08d}-"),
             'DYNTEAM_RESOURCE_SYSTEM_UNIQUE_ORIGINAL_SEQUENCE')
        seen.add(intent['sequence']);absent=directory/'NOT_STARTED_PUBLIC.json';terminal=directory/'TERMINAL_PUBLIC.json'
        if absent.exists():
            need(not terminal.exists(),'DYNTEAM_SYSTEM_CANNOT_BE_UNSENT_AND_TERMINAL')
            raw,_=O.read(absent);v=O.SelectedJSON(raw.decode('utf-8','strict')).select({'PUBLIC_code','sequence','request_replays'})
            need(v['PUBLIC_code']=='DYNTEAM_SYSTEM_PROBE_POPEN_NOT_STARTED' and v['sequence']==intent['sequence'] and
                 v['request_replays']==0,'DYNTEAM_SYSTEM_NOT_STARTED_EXACT_PUBLIC_RECORD')
            continue
        if not terminal.exists():occupied+=1;continue
        raw,_=O.read(terminal);required={'schema','sequence','contract_sha256','http_status','completed_at'}
        v=_optional_system_controls(O.SelectedJSON(raw.decode('utf-8','strict')),required|{'stream','stream_complete','reported_tokens'})
        need(required<=set(v),'DYNTEAM_SYSTEM_REQUIRED_LEGACY_TERMINAL_FIELDS')
        need('stream'not in v or type(v['stream'])is bool,'DYNTEAM_SYSTEM_STREAM_MARKER_BOOLEAN')
        status=v['http_status'];need(v['schema']=='count14-dynteam-system-probe-terminal-v1' and
             v['sequence']==intent['sequence'] and v['contract_sha256']==contract_sha256 and
             (status is None or type(status) is int and 100<=status<=599),'DYNTEAM_SYSTEM_HTTP_TERMINAL_FIXED_ENUM')
        unknown=status is None or status==200 and v.get('stream')is True and v.get('stream_complete')is not True
        occupied+=int(unknown)
        at=O.datetime.datetime.fromisoformat(v['completed_at']);need(at.tzinfo is not None,'DYNTEAM_SYSTEM_SOURCE_TIMESTAMP')
        if now-600*10**9<int(at.timestamp()*10**9)<=now:calls+=1;bad+=int(unknown or status>=500 or status==200 and v.get('stream')is True and not (type(v.get('reported_tokens'))is int and v['reported_tokens']>0))
    need(occupied<=2,'DYNTEAM_SYSTEM_RESERVED2_NOT_FORGIVEN')
    return dict(root=str(home),FP8_inflight=occupied,terminals=calls,errors=bad,observed_ns=now)


def kernel_projection(mounts,*,findmnt=Path('/usr/bin/findmnt')):
    """Actual fixed kernel/VFS projections. Caller checks real scratch mounts.

    /tmp OWN tests truthfully return is_mount=False/same-rootfs; there is NO
    positive mount virtualization or inferred free-space credit in this helper.
    """
    need(type(mounts) is dict and set(mounts)=={'scratch1_SEARCH_layers','scratch2_roots_snapshots'},
         'DYNTEAM_RESOURCE_TWO_EXPLICIT_FILESYSTEMS')
    available=None
    with open('/proc/meminfo','rb') as source:
        for line in source:
            if line.startswith(b'MemAvailable:'):available=int(line.split()[1])*1024;break
    need(type(available) is int and available>=0,'DYNTEAM_RESOURCE_REAL_MEMAVAILABLE')
    rootdev=Path('/').stat().st_dev;rows={}
    for name,value in mounts.items():
        p=Path(value);need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and p.is_dir(),
                           'DYNTEAM_RESOURCE_CANONICAL_MOUNT_PATH')
        fs=os.statvfs(p)
        result=subprocess.run([str(findmnt),'-T',str(p),'-n','-o','UUID'],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=2.5,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        need(result.returncode==0 and len(result.stdout)<=4096,'DYNTEAM_RESOURCE_FIXED_MOUNT_UUID_PROJECTION')
        value=result.stdout.decode('ascii','strict').strip()
        rows[name]=dict(path=str(p),device=p.stat().st_dev,rootfs_device=rootdev,is_mount=os.path.ismount(p),
                       mount_uuid=value or None,available_bytes=fs.f_bavail*fs.f_frsize)
    return dict(observed_ns=time.time_ns(),MemAvailable_bytes=available,storage=rows)


def _socket_peer(path,birth):
    need(type(birth) is ProcessBirth and process_birth(birth.pid)==birth,
         'DYNTEAM_RESOURCE_EXACT_DAEMON_PROCESS_BIRTH')
    path=Path(path);need(path.resolve()==path and not path.is_symlink() and stat.S_ISSOCK(path.stat().st_mode),
                         'DYNTEAM_RESOURCE_PRIVATE_DAEMON_SOCKET')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
        peer.settimeout(2.5);peer.connect(str(path))
        need(struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))==
             (birth.pid,birth.uid,birth.gid),'DYNTEAM_RESOURCE_EXACT_SOCKET_PEER_NOT_PID_GUESS')


def docker_projection(docker,*,dockerd_birth,containerd_socket,containerd_birth,images):
    """Exact daemon/peer/image proof, no system Docker or mutable tag fallback.

    For production, private containerd must be explicitly selected by dockerd
    or be its genuine managed child. /proc reads are limited to these two
    registered infrastructure processes, never scientific argv or stacks.
    """
    need(type(docker) is ScopedDocker and type(images) is list and images,
         'DYNTEAM_RESOURCE_SCOPED_DOCKER_AND_FROZEN_IMAGE_PINS')
    docker.verify_daemon();r=docker.route
    _socket_peer(r.socket_path,dockerd_birth);_socket_peer(containerd_socket,containerd_birth)
    c=Path(containerd_socket)
    if r.qualification_only:
        need(any(v.startswith('OWN-') for v in c.parts),'DYNTEAM_OWN_CONTAINERD_EXACT_FIXTURE')
    else:
        need(dockerd_birth.uid==containerd_birth.uid==0 and
             any(c.is_relative_to(base) for base in ('/mnt/ptb-scratch','/mnt/ptb-scratch2')),
             'DYNTEAM_RESOURCE_NO_SYSTEM_CONTAINERD_SOCKET')
        args=Path('/proc',str(dockerd_birth.pid),'cmdline').read_bytes().split(b'\0');selected=[]
        for i,arg in enumerate(args):
            if arg==b'--containerd':need(i+1<len(args),'DYNTEAM_DOCKER_CONTAINERD_FLAG');selected.append(args[i+1])
            elif arg.startswith(b'--containerd='):selected.append(arg[len(b'--containerd='):])
        if selected:need(selected==[os.fsencode(str(c))],'DYNTEAM_RESOURCE_DOCKER_EXACT_PRIVATE_CONTAINERD_FLAG')
        else:
            raw=Path('/proc',str(containerd_birth.pid),'stat').read_bytes();fields=raw.rsplit(b') ',1)[1].split()
            need(int(fields[1])==dockerd_birth.pid,'DYNTEAM_RESOURCE_GENUINE_MANAGED_CONTAINERD_CHILD')
    seen=set()
    for pin in images:
        need(type(pin) is dict and set(pin)=={'id','digests','layers'} and type(pin['id']) is str and
             pin['id'].startswith('sha256:') and sha64(pin['id'][7:]) and type(pin['digests']) is list and
             all(type(x) is str for x in pin['digests']) and type(pin['layers']) is list and
             all(type(x) is str for x in pin['layers']) and pin['id'] not in seen,
             'DYNTEAM_RESOURCE_UNIQUE_IMMUTABLE_IMAGE_METADATA')
        seen.add(pin['id']);actual=docker._project('image','inspect',pin['id'],'--format',IMAGE)
        need(set(actual)==set(pin) and actual['id']==pin['id'] and sorted(actual['digests'] or [])==sorted(pin['digests']) and
             actual['layers']==pin['layers'],'DYNTEAM_RESOURCE_FRESH_ID_DIGEST_ORDERED_LAYER_MATCH')
    # Repeat identity AFTER all external metadata commands, no stale peer proof.
    _socket_peer(r.socket_path,dockerd_birth);_socket_peer(c,containerd_birth);docker.verify_daemon()
    return dict(docker_host='unix://'+str(r.socket_path),daemon_id=r.daemon_id,data_root=str(r.data_root),
        healthy=True,uses_system_containerd=False,system_fallback=False,immutable_image_identity_verified=True,
        existing_daemon_content_overwritten=False,OWN_private_containerd_link_not_production_proof=r.qualification_only,
        verified_images=len(images),observed_ns=time.time_ns())
