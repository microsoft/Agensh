"""Own original watchdog -> exact team-idle PUBLIC metadata producer (WIP).

No new watcher/model dispatcher. Same native watchdog child must return first.
Only fixed COUNT, activity/role/birth booleans and pinned framework code read.
All synchronous diagnostic subprocess calls have finite timeouts outside locks.
"""
from pathlib import Path
from dataclasses import asdict
import hashlib
import os
import subprocess
import time
from common import need,digest
from native_peer_registry import process_birth
from native_idle_runtime import read_json,append
from formal_natural_cut import NativeTeamIdleSample
from formal_natural_abi import POLICY_SHA

# Same native framework event state predicate as original watchdog_uem_pending,
# across the exact private mysql scope. No payload JSON, account or body access.
SQL="SELECT COUNT(*) FROM events WHERE (state IN ('pending','sending','retrying') OR (state='failed' AND attempts<5 AND next_retry_at IS NOT NULL));"
SCRIPT='''set -eu
set -a
source "$ENV_FILE"
set +a
exec "$COUNT14_NATIVE_DOCKER" --host "$COUNT14_NATIVE_DOCKER_SOCKET" exec "$MYSQL_CONTAINER" mysql -N -B -uroot "-p$MYSQL_ROOT_PASSWORD" -D omcgitea -e "$COUNT14_NATURAL_PENDING_SQL"
'''


class NativeTeamIdleSampler:
    def __init__(self,cohort):
        from native_formal_cohort import NativeFormalCohort
        from native_idle_watchdog import NativeIdleWatchdog
        need(type(cohort)is NativeFormalCohort and type(getattr(cohort,'native_idle_watchdog',None))is NativeIdleWatchdog and
             not cohort.activation_attempted and set(cohort.core.gate.startup_held)==set(cohort.tracks),
             'FORMAL_NATURAL_SAMPLER_ONLY_ORIGINAL_COLD_WATCHDOG')
        self.cohort,self.core,self.watchdog=cohort,cohort.core,cohort.native_idle_watchdog
        self.birth=process_birth(os.getpid());self.accepted={};self.failures={};self.sequence={t:0 for t in cohort.tracks}
        self.runtime=Path(__file__).with_name('formal_natural_idle_runtime.py')
        self.source_sha256=digest(dict(runtime=hashlib.sha256(self.runtime.read_bytes()).hexdigest(),
            fixed_pending_SQL_sha256=hashlib.sha256(SQL.encode()).hexdigest(),policy_sha256=POLICY_SHA,
            original_native_functions=self.watchdog.source_proofs))
        need(all(r['ordinal']==0 and r['child']is None for r in self.watchdog.rows.values()),
             'FORMAL_NATURAL_RUNTIME_GATE_BEFORE_ANY_NATIVE_TICK_OR_POST')
        self.watchdog.runtime=self.runtime
        self.watchdog.runtime_sha256=hashlib.sha256(self.runtime.read_bytes()).hexdigest()

    def outside(self):
        need(process_birth(os.getpid())==self.birth and not self.core.ledger.mutex._is_owned(),
             'FORMAL_NATURAL_READONLY_DIAGNOSTICS_NO_SCIENCE_LOCK_OR_NEW_OWNER')

    def sample(self,t):
        self.outside();w=self.watchdog;row=w.rows[t];track=self.cohort.tracks[t]
        if row['child']is not None or row['failure']is not None or row['closed'] or row['held'] or row['ordinal']==0:return None
        if track['checkpoint'].state!='RUNNING' or track['host'].held:return None
        with self.core.ledger.mutex:
            f=self.core.ledger.frontier(t)
            roles=tuple(sorted(role for (trajectory,role) in self.core.roles.births if trajectory==t and role.startswith('worker-')))
            births=digest({role:asdict(value) if hasattr(value,'__dataclass_fields__')else value for (trajectory,role),value in self.core.roles.births.items() if trajectory==t})
        if not roles or f['state']!='RUNNING' or f['reserved'] or f['unresolved'] or f['active_operations']:return None
        tick=read_json(row['home']/'CURRENT_TICK_PUBLIC.json',8192)
        active=self.core.active_clock.read(t)['active_ns']//1_000_000_000
        if active<tick['active_seconds'] or active-tick['active_seconds']>60:return None
        eligibility={}
        for role in roles:
            p=row['home']/f"N{tick['ordinal']:08d}-{role}-ELIGIBLE_PUBLIC.json"
            if not p.exists():return None
            value=read_json(p,8192)
            need(value.get('tick')==tick['ordinal'] and value.get('role')==role and
                 value.get('owner')==[self.birth.pid,self.birth.start_ticks,self.birth.boot_id] and
                 value.get('active_seconds')==tick['active_seconds'] and value.get('original_native_conditions_passed')is True and
                 value.get('POST_performed')is False,'FORMAL_NATURAL_CURRENT_ORIGINAL_ELIGIBILITY_RECEIPT')
            eligibility[role]=value
        http=self.core.servers[t]
        if not http.trajectory_park_ready(t)['safe_to_park_writers'] or http.lifecycle_storage_unknown:return None
        if self.core.membership_fences[t].public_counts()['pending_native_effects']:return None
        host=self.core.native_host_environment['trajectories'][t]
        mysql=self.core.cold_bootstrap.infra_birth_records[t,'mysql']
        env=dict(PATH='/usr/bin:/bin',HOME=str(row['home']),LANG='C.UTF-8',**host['launcher_env'],
            ENV_FILE=host['envfile'],MYSQL_CONTAINER=mysql['cid'],COUNT14_NATURAL_PENDING_SQL=SQL)
        # Real finite native metadata query; unknown/error is never coerced 0.
        result=subprocess.run(['/bin/bash','-c',SCRIPT],cwd=host['project_root'],env=env,
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20)
        raw=result.stdout.strip()
        if result.returncode or len(raw)>16 or not raw.isdigit() or int(raw)!=0:return None
        with self.core.ledger.mutex:
            after=digest({role:asdict(value) if hasattr(value,'__dataclass_fields__')else value for (trajectory,role),value in self.core.roles.births.items() if trajectory==t})
            now=self.core.ledger.frontier(t)
        after_active=self.core.active_clock.read(t)['active_ns']//1_000_000_000
        if after_active<tick['active_seconds'] or after_active-tick['active_seconds']>60:return None
        if after!=births or any(now[k]!=f[k] for k in ('generation','state','actual','reserved','unresolved','active_operations')):return None
        # Eligibility itself proves >=600 from the original native active clock;
        # do not mix wall/log mtime and active-clock domains here.
        sample=NativeTeamIdleSample(t,digest(dict(tick=tick['ordinal'],roles=eligibility,births=births)),
            self.source_sha256,600,0,0,0,len(roles),roles,True,0,True)
        self.accepted[t]=(sample,tick['ordinal'],births,active)
        return sample

    def accepts_current_sample(self,sample,t):
        self.outside();entry=self.accepted.get(t)
        if entry is None or sample is not entry[0]:return False
        row=self.watchdog.rows[t]
        with self.core.ledger.mutex:
            births=digest({role:asdict(value) if hasattr(value,'__dataclass_fields__')else value for (trajectory,role),value in self.core.roles.births.items() if trajectory==t})
        active=self.core.active_clock.read(t)['active_ns']//1_000_000_000
        return row['child']is None and row['ordinal']==entry[1] and not row['held'] and not row['closed'] and births==entry[2] and 0<=active-entry[3]<=60

    def allow_original_neutral_after_release(self,t,meta,snapshot):
        self.outside();row=self.watchdog.rows[t]
        need(meta['trajectory']==t and meta['policy_sha256']==POLICY_SHA and self.watchdog.physical_clear(t),
             'FORMAL_NATURAL_RELEASE_SAME_OWNER_AFTER_METADATA_PHYSICAL_DRAIN')
        value=dict(schema='count14-formal-native-first-natural-release-v1',trajectory=t,
            owner=[self.birth.pid,self.birth.start_ticks,self.birth.boot_id],natural_stop=meta,snapshot=snapshot,
            control_home=str(row['home']),organization=row['org'],
            snapshot_and_K3_queued=True,original_same_live_thaw_complete=True)
        path=row['home']/'FIRST_NATURAL_RELEASE_PUBLIC.json'
        if path.exists():need(read_json(path)==value,'FORMAL_NATURAL_RELEASE_ONCE_IDENTICAL')
        else:append(path,value)
