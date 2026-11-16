"""msg236: anonymous first-2M observations, track-local UNSENT admission hold.

No prompt, candidate, response delta, request ID or credential is exported.
Only existing metadata/counts are read; fees and request rows are never changed.
There is deliberately NO resume/clear/replay method. A latched hold survives
cold recovery as an append-only control event. Fixes require frozen cold code.
"""
from pathlib import Path
import hashlib
import json
import os
import statistics
import stat
import subprocess
import time


def _wire(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


class FormalEarlySanity:
    WINDOW = 2_000_000
    REPORT_SECONDS = 1800

    def __init__(self, core):
        assert core.contract['mode'] == 'production' and len(core.rows) == 6
        assert not hasattr(core.gate, 'formal_early_sanity')
        self.core, self.ledger = core, core.ledger
        self.counts = {t: None for t in core.rows}
        self.count_errors = {t: None for t in core.rows}
        self.count_at_n = {t: -1 for t in core.rows}
        self.next_counts = {t: 0. for t in core.rows}
        self.next_report = {t: time.monotonic()+self.REPORT_SECONDS for t in core.rows}
        self.reported_hold = set()
        self.home = Path(core.home)/'formal-early-sanity'
        if not self.home.exists():
            self.home.mkdir(mode=0o700, exist_ok=False)
        info = self.home.lstat()
        assert self.home.resolve() == self.home and not self.home.is_symlink()
        assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700
        core.formal_early_sanity = core.gate.formal_early_sanity = self

    def _snapshot(self, t):
        """Called under the original ledger mutex; no private state queries."""
        roles = self.core.rows[t]['roles']
        response = {r: [] for r in roles}
        # This event contains ONLY V5/V7 anonymous receipt fields. Do not query
        # REQUEST_PAYLOAD_PIN, private continuations, task or tool bodies.
        rows = self.ledger.db.execute(
            "SELECT metadata FROM events WHERE trajectory=? AND kind='ANONYMOUS_MODEL_RESPONSE_SANITY' ORDER BY seq", (t,)).fetchall()
        prefix_tokens = 0
        missing_usage = 0
        for (raw,) in rows:
            if prefix_tokens >= self.WINDOW:
                break
            m = json.loads(raw)
            role = m.get('role')
            if role not in response:
                raise ValueError('FORMAL_EARLY_SANITY_UNKNOWN_ROLE')
            response[role].append(m)
            a, b = m.get('reported_input_tokens'), m.get('reported_output_tokens')
            if type(a) is int and type(b) is int and a >= 0 and b >= 0:
                prefix_tokens += a+b
            else:
                missing_usage += 1
        request_rows = self.ledger.db.execute(
            "SELECT role,state,COUNT(*) FROM requests WHERE trajectory=? GROUP BY role,state", (t,)).fetchall()
        grouped = {r: {} for r in roles}
        for role, state, number in request_rows:
            grouped[role][state] = number
        native = self.counts[t]
        items = {}
        all_output, empty_both, tool_nonempty, nresponses, finishes = [], 0, 0, 0, {}
        for role in roles:
            samples = response[role]
            outputs = [m['reported_output_tokens'] for m in samples
                       if type(m.get('reported_output_tokens')) is int]
            booleans = {}
            for name in ('content', 'reasoning', 'tool_calls','mapped_content','mapped_reasoning','mapped_tool_calls'):
                field = ('mapped_reasoning_item_present' if name == 'mapped_reasoning' else
                         name+'_nonempty' if name.startswith('mapped_') else 'upstream_'+name+'_nonempty')
                values = [m.get(field) for m in samples]
                known = sum(type(v) is bool for v in values)
                booleans[name] = dict(nonempty=sum(v is True for v in values), observed=known,
                                      ratio=(sum(v is True for v in values)/known if known else None))
            fr = {}
            for m in samples:
                for name, count in m.get('upstream_finish_reason_counts', {}).items():
                    key = name if name in ('stop','length','tool_calls','content_filter','OTHER') else 'OTHER'
                    if type(count) is not int or count < 0:
                        raise ValueError('FORMAL_EARLY_SANITY_INVALID_FINISH_COUNT')
                    fr[key] = fr.get(key, 0)+count
                    finishes[key] = finishes.get(key, 0)+count
                a, b = m.get('mapped_content_nonempty'), m.get('mapped_tool_calls_nonempty')
                if type(a) is bool and type(b) is bool:
                    nresponses += 1
                    empty_both += int(not a and not b)
                    tool_nonempty += int(b)
            states = grouped[role]
            items[role] = dict(requests=sum(v for k,v in states.items() if k != 'CANCELLED_UNSENT'),
                request_state_counts=states, anonymous_receipts=len(samples), finish_reason=fr,
                output_median=statistics.median(outputs) if outputs else None,
                output_max=max(outputs) if outputs else None, nonempty=booleans,
                CLAIM=None if native is None else native[role], UNKNOWN=states.get('UNKNOWN',0))
            all_output.extend(outputs)
        spawns = self.ledger.db.execute(
            "SELECT json_extract(metadata,'$.worker_slot'),COUNT(*) FROM events WHERE trajectory=? AND kind='DYNTEAM_NATIVE_SPAWN_COMMITTED' GROUP BY json_extract(metadata,'$.worker_slot')", (t,)).fetchall()
        spawn = sum(number for _,number in spawns)
        for role in items:
            items[role]['spawn'] = 0
        for slot,number in spawns:
            assert type(slot) is int and 1 <= slot <= 32
            items['worker-'+str(slot-1).zfill(2)]['spawn'] += number
        claims = None if native is None else sum(native.values())
        return dict(schema='count14-formal-early-sanity-msg236-v1', trajectory=t,
            observed_ns=time.time_ns(), window_SEARCH_tokens=self.WINDOW,
            reported_SEARCH_tokens_in_observed_prefix=prefix_tokens, per_role=items,
            output_sample_count=len(all_output),
            output_median=statistics.median(all_output) if all_output else None,
            output_max=max(all_output) if all_output else None, finish_reason=finishes,
            anonymous_complete_field_observations=nresponses,
            content_and_tool_calls_both_empty=empty_both,
            content_and_tool_calls_both_empty_ratio=empty_both/nresponses if nresponses else None,
            tool_calls_nonempty=tool_nonempty, CLAIM=claims, spawn=spawn,
            UNKNOWN=sum(v['UNKNOWN'] for v in items.values()),
            receipts_without_reported_usage=missing_usage,
            native_count_error_type=self.count_errors[t],
            metadata_only_no_model_or_body_read=True)

    def check(self, t):
        """Exact per-track hold checked before the ORIGINAL reserve/send."""
        with self.ledger.mutex:
            old = self.ledger.db.execute(
                "SELECT 1 FROM events WHERE trajectory=? AND kind='FORMAL_EARLY_SANITY_HOLD' LIMIT 1", (t,)).fetchone()
            if old:
                return True
            value = self._snapshot(t)
            reasons = []
            ratio = value['content_and_tool_calls_both_empty_ratio']
            if ratio is not None and ratio > .30:
                reasons.append('CONTENT_AND_TOOLS_EMPTY_GT_30_PERCENT')
            completed = sum(x['anonymous_receipts'] for x in value['per_role'].values())
            if completed != value['anonymous_complete_field_observations']:
                reasons.append('MAPPED_FIELD_METADATA_UNAVAILABLE_NO_ASSUMED_FALSE_OR_HEALTH')
            if completed >= 20 and completed == value['anonymous_complete_field_observations'] and value['tool_calls_nonempty'] == 0:
                if value['CLAIM'] == 0 and self.count_at_n[t] >= completed:
                    reasons.append('AFTER20_CLAIM0_AND_TOOLS0')
                elif value['CLAIM'] is None and self.count_errors[t] is not None:
                    reasons.append('CLAIM_COUNT_UNAVAILABLE_NO_ASSUMED_ZERO_OR_HEALTH')
                elif value['CLAIM'] in (None, 0) and self.count_at_n[t] < completed:
                    # Original UNSENT waiter parks until the owner reads the
                    # real count. Unknown is not zero, nor a latched finding.
                    if not reasons:
                        return True
            # Missing V5/V7 data must not be represented as false or healthy.
            accounted = sum(x['request_state_counts'].get('SETTLED',0) for x in value['per_role'].values())
            if value['reported_SEARCH_tokens_in_observed_prefix'] < self.WINDOW and accounted > completed:
                reasons.append('ANONYMOUS_RECEIPT_UNAVAILABLE_NO_ASSUMED_HEALTH')
            if not reasons:
                return False
            with self.ledger.tx():
                self.ledger.event(t, 'FORMAL_EARLY_SANITY_HOLD', dict(reasons=reasons,
                    pause_new_release_only=True, cancel_sent=False, replay=False,
                    output_median=value['output_median'], empty_both_ratio=ratio,
                    CLAIM=value['CLAIM'], tool_calls_nonempty=value['tool_calls_nonempty']))
            self.ledger.capacity_changed.notify_all()
            return True

    def observe(self, t):
        # Called after original settlement, never cancels or changes a paid row.
        self.check(t)

    def _claims(self, t):
        """Exact registered MySQL; read-only aggregate, never SELECT body."""
        from native_host_environment import infra_labels
        from native_peer_registry import process_birth
        docker = self.core.native_containers.docker
        registration = self.core.cold_bootstrap.infra_birth_records[(t,'mysql')]
        cid = registration['cid']
        state = docker.inspect(cid)
        labels = infra_labels(self.core,t,'mysql')
        expected = {k:labels[v] for k,v in {'root':'count14.root','trajectory':'count14.trajectory-sha256',
            'contract':'count14.contract-sha256','role':'count14.role','component':'count14.component'}.items()}
        assert state['labels'] == expected and state['running'] and state['image'] == registration['image_id']
        assert process_birth(state['pid']) == registration['init_birth']
        org = self.core.native_layout.current(t)['org']
        from native_beta_layout import native_aliases
        aliases = {org+'-'+v['native_short']:r for r,v in native_aliases(self.core.rows[t]['arm']).items()}
        def query(sql):
            child = subprocess.run(docker.argv('exec','-i',cid,'sh','-c',
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --protocol=socket --user=root --batch --skip-column-names --raw'),
                input=('START TRANSACTION READ ONLY;\n'+sql+'\nROLLBACK;\n').encode(),
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
            assert child.returncode == 0 and len(child.stdout) <= 65536
            return child.stdout.decode().splitlines()
        databases = query("SELECT table_schema FROM information_schema.tables WHERE table_name='board_gists' AND table_schema NOT IN ('mysql','sys','performance_schema','information_schema');")
        assert len(databases) == 1 and databases[0].replace('_','').isalnum() and databases[0].isascii()
        lines = query("SELECT JSON_OBJECT('actor',account,'count',COUNT(*)) FROM `"+databases[0]+"`.board_gists WHERE type='CLAIM' GROUP BY account;")
        result = {r:0 for r in self.core.rows[t]['roles']}
        for line in lines:
            row = json.loads(line)
            assert set(row) == {'actor','count'} and row['actor'] in aliases
            assert type(row['count']) is int and row['count'] >= 0
            result[aliases[row['actor']]] += row['count']
        return result

    def poll(self):
        """Original owner polling only; no background dispatcher/model probe."""
        now = time.monotonic()
        for t in self.core.rows:
            with self.ledger.mutex:
                value = self._snapshot(t)
            completed = sum(v['anonymous_receipts'] for v in value['per_role'].values())
            due = now >= self.next_report[t]
            held = self.check(t)
            first_hold = held and t not in self.reported_hold
            need_claim = (completed >= 20 and value['tool_calls_nonempty'] == 0 and
                          (self.counts[t] is None or value['CLAIM'] == 0) and self.count_at_n[t] < completed)
            if (due or need_claim or first_hold) and now >= self.next_counts[t] and completed:
                try:
                    self.counts[t] = self._claims(t)
                    self.count_errors[t] = None
                    self.count_at_n[t] = completed
                    self.core.gate.notify()
                except Exception as error:
                    self.count_errors[t] = type(error).__name__
                self.next_counts[t] = now+60
            held = self.check(t)
            if not due and not (held and t not in self.reported_hold):
                continue
            with self.ledger.mutex:
                value = self._snapshot(t)
            if value['reported_SEARCH_tokens_in_observed_prefix'] >= self.WINDOW and not held and not due:
                continue
            value['new_release_paused'] = held
            target = self.home/(hashlib.sha256(t.encode()).hexdigest()+'.json')
            tmp = target.with_name('.'+target.name+'-'+str(os.getpid()))
            raw = _wire(value)
            fd = os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
            try:
                with os.fdopen(fd,'wb',closefd=False) as out:
                    out.write(raw);out.flush();os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp,target)
            self.next_report[t] = now+self.REPORT_SECONDS
            if held:
                self.reported_hold.add(t)
