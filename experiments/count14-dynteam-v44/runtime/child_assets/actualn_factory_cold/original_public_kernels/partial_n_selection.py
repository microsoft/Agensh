"""Read-only preparation from the ORIGINAL queue and ledger, never score JSON.

No install/apply, DB write, wait/poll, child launch or scientific file read is
performed. Runtime publication must revalidate this snapshot after the native
subset audit and atomically append the final point disposition. That writing
suffix is deliberately not claimed as delivered by this component.
"""
from pathlib import Path
import re
from common import need, digest, strict
from durable_final import durable_wait, ended
from partial_n_policy import decide_attempts


class BusyBoundary(RuntimeError):
    pass


def native_paths(records, label, setting):
    """Use each ORIGINAL job.replicate, never enumerate(selected,1)."""
    out = []
    for r in sorted(records, key=lambda x: x['job']['replicate']):
        j = r['job']
        k = j['replicate']
        attempt = j.get('attempt', 1)
        root = Path(r['config']['aux_root'])
        paths = dict(branch=root / f'k{k}',
                     aggregate=root / 'results' / setting /
                     (label + f'-k{k}') / 'aggregate.json',
                     matrix=root / 'evaluator-private' / setting /
                     (label + f'-k{k}'),
                     custody=root / f'k{k}' / 'physical-custody.json')
        if attempt > 1:
            paths['attempt'] = attempt
        out.append(dict(replicate_id=k, paths=paths))
    return out


def _point_rows(q, point_id):
    """Enumerate all structural job tables, including any additive a4 table.

    The historical all_rows implementation may not know a new table; silently
    dropping it could turn QUEUED into a false terminal. No SQL or log body is
    exported. Both the trusted queue object and actual rows are authoritative.
    """
    out = []
    tables = [r[0] for r in q.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    required = {'id', 'point', 'replicate', 'state', 'claim', 'child',
                'terminal', 'result'}
    for table in tables:
        need(type(table) is str and
             re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', table),
             'PN_SAFE_REGISTERED_TABLE_IDENTIFIER')
        cols = {r[1] for r in q.db.execute('PRAGMA table_info("' + table + '")')}
        if not required <= cols:
            continue
        attempt = 'j.attempt' if 'attempt' in cols else '1'
        sql = ('SELECT j.*,p.trajectory,p.setting,p.target,p.input_root,'
               'p.input_policy,' + attempt + ' AS original_attempt FROM "' +
               table + '" j JOIN points p ON j.point=p.point '
               'WHERE j.point=? ORDER BY j.replicate,original_attempt')
        for row in q.db.execute(sql, (point_id,)):
            row = dict(row)
            row['attempt'] = row.pop('original_attempt')
            out.append(row)
    need(len({r['id'] for r in out}) == len(out),
         'PN_DUPLICATE_ORIGINAL_JOB_ACROSS_TABLES')
    return sorted(out, key=lambda r: (r['replicate'], r['attempt']))


def _failed_proof(q, j, partial, allocation):
    """Certify persisted original PARTIAL+SYSTEM cost, no redisposition."""
    need(type(partial) is type(allocation) is dict,
         'PN_PERSISTED_PARTIAL_AND_SYSTEM_ALLOCATION')
    for row in (partial, allocation):
        need(row.get('point_id') == j['point'] and
             row.get('replicate_id') == j['replicate'] and
             row.get('attempt') == j['attempt'] and
             row.get('allocation') == 'SYSTEM_CONSUMPTION' and
             row.get('billing_domain') == 'AUX_FINALIZATION' and
             row.get('search_budget_delta') == 0,
             'PN_ORIGINAL_DISPOSITION_AND_BILLING_DOMAIN')
    need(partial.get('disposition') == 'PARTIAL' and
         partial.get('original_claim') == allocation.get('claim') == j['claim']
         and allocation.get('job_id') == j['id'],
         'PN_ORIGINAL_PARTIAL_ALLOCATION_CLAIM')
    durable = partial.get('schema') == 'disk-final-logical-disposition-proof-v1'
    orphan = durable and partial.get('custody_provenance', {}).get('custody') == 'ORIGINAL_PARENT_LOST_CHILD_PHYSICALLY_ENDED'
    if orphan:
        provenance = partial['custody_provenance']
        need(j['state'] == 'RUNNING' and j['terminal'] is None and
             provenance == dict(custody='ORIGINAL_PARENT_LOST_CHILD_PHYSICALLY_ENDED',
                 original_child=strict(j['child'].encode()), wait_observed=False,
                 exit_code=None, signal=None, original_claim=j['claim'],
                 original_raw_state='RUNNING', original_terminal_remains_null=True),
             'PN_ORIGINAL_ORPHAN_CUSTODY_NO_BACKFILLED_WAIT')
        prior = q.db.execute('SELECT metadata FROM disk_orphan_dispositions WHERE id=?', (j['id'],)).fetchone()
        need(prior is not None and strict(prior[0].encode()) == provenance and
             ended(provenance['original_child']), 'PN_ORIGINAL_ORPHAN_STILL_PHYSICALLY_ENDED')
        t = None
        custody_sha = digest(provenance)
    else:
        t = durable_wait(q, j)
        need(t['exit_code'] != 0 or t['signal'] is not None,
             'PN_EXIT0_HOLD_IS_NOT_FAILED_PARTIAL')
        custody_sha = digest(t)
    if durable:
        if not orphan:
            provenance = dict(custody='GENUINE_DURABLE_PARENT_WAIT',
                          original_terminal_sha256=digest(t),
                          original_claim=j['claim'])
        need(partial.get('custody_provenance') ==
             allocation.get('custody_provenance') == provenance,
             'PN_ORIGINAL_DURABLE_WAIT_PROVENANCE')
        extra_fields = ('logical_model_unresolved',
                        'physical_unknown_slots_retained',
                        'unknown_aux_reservation_charge')
        need(all(type(partial.get(k)) is int and partial[k] >= 0
                 for k in extra_fields) and
             partial['logical_model_unresolved'] == 0,
             'PN_DISPOSED_LOGICAL_CUSTODY_UNKNOWN_RETAINED')
    else:
        need(partial.get('terminal_sha256') ==
             allocation.get('terminal_sha256') == digest(t) and
             partial.get('model_unresolved') == 0,
             'PN_ORIGINAL_NATIVE_TERMINAL_AND_CUSTODY')
        extra_fields = ()
    fields = ('scope', 'model_unresolved', 'evaluator_unresolved',
              'native_aux_tokens', 'native_request_count',
              'native_ledger_sha256', 'evaluator_proof_sha256') + extra_fields
    need(all(k in partial and partial[k] == allocation.get(k) for k in fields),
         'PN_EXACT_SAME_PERSISTED_COST_PROOF')
    need(type(partial.get('model_unresolved')) is int and partial['model_unresolved'] >= 0 and
         type(partial.get('evaluator_unresolved')) is int and
         partial['evaluator_unresolved'] == 0,
         'PN_FAILED_EVALUATOR_CUSTODY_CLOSED')
    return dict(job_id=j['id'], point_id=j['point'], scope=partial['scope'],
                original_claim=j['claim'], custody_proof_sha256=custody_sha,
                proof_kind='ORIGINAL_ORPHAN_PHYSICALLY_ENDED_NO_WAIT' if orphan else 'GENUINE_FAILED_WAIT',
                wait_observed=not orphan,
                terminal_sha256=None if orphan else digest(t),
                exit_code=None if orphan else t['exit_code'],
                signal=None if orphan else t['signal'],
                native_request_count=partial['native_request_count'],
                native_aux_tokens=partial['native_aux_tokens'],
                unknown_aux_reservation_charge=
                    partial['unknown_aux_reservation_charge'] if durable else 0,
                physical_unknown_slots_retained=
                    partial['physical_unknown_slots_retained'] if durable else 0,
                original_partial_sha256=digest(partial),
                original_SYSTEM_allocation_sha256=digest(allocation))


def prepare_selection(dispatcher, point_id, *, original_limit,
                      last_extra_grants=None, tool_exemptions=None):
    """Read original rows and return qualified-candidate/terminal PREPARATION.

    original_limit must be derived by the eventual owner adapter from sealed
    regular/natural policy. last_extra_grants/tool_exemptions must come from
    owner-authenticated original receipt bytes, not a worker-supplied object.
    No caller-controlled terminal flag is consumed. Every failed attempt must
    have a matching append-only event, original claim and SYSTEM allocation.
    """
    d = dispatcher
    q, ledger = d.queue, d.ledger
    last_extra_grants = {} if last_extra_grants is None else last_extra_grants
    tool_exemptions = {} if tool_exemptions is None else tool_exemptions
    if not ledger.mutex.acquire(False):
        raise BusyBoundary('PN_LEDGER_BUSY_NO_CHANGE')
    try:
        if not q.mutex.acquire(False):
            raise BusyBoundary('PN_QUEUE_BUSY_NO_CHANGE')
        try:
            jobs = _point_rows(q, point_id)
            need(bool(jobs) and {j['replicate'] for j in jobs} == {1, 2, 3},
                 'PN_ALL_THREE_ORIGINAL_REPLICATE_SLOTS_REQUIRED')
            descriptors = {(j['trajectory'], j['setting'], j['target'],
                            j['input_root'], j['input_policy']) for j in jobs}
            need(len(descriptors) == 1, 'PN_SAME_FROZEN_POINT_DESCRIPTOR')
            current_ids = {j['id'] for j in jobs}
            last_extra_grants = {k:v for k,v in last_extra_grants.items() if k in current_ids}
            tool_exemptions = {k:v for k,v in tool_exemptions.items() if k in current_ids}
            partials = {}
            allocations = {}
            selected = {}
            decisions = {}
            failure_costs = []
            for k in (1, 2, 3):
                chain = []
                for j in [j for j in jobs if j['replicate'] == k]:
                    row = dict(point_id=point_id, replicate_id=k,
                               attempt=j['attempt'], job_id=j['id'],
                               state=j['state'])
                    grant = last_extra_grants.get(j['id'])
                    if grant is not None:
                        row.update(last_extra=True,
                                   last_extra_grant_sha256=grant)
                    p = q.db.execute(
                        'SELECT metadata FROM replicate_partials WHERE job_id=?',
                        (j['id'],)).fetchone()
                    if p is not None:
                        p = strict(p[0].encode())
                        a = ledger.db.execute(
                            'SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',
                            (j['id'],)).fetchone()
                        need(a is not None, 'PN_ORIGINAL_SYSTEM_ALLOCATION_MISSING')
                        a = strict(a[0].encode())
                        proof = _failed_proof(q, j, p, a)
                        partials[j['id']], allocations[j['id']] = p, a
                        failure_costs.append(proof)
                        row.update(state='PARTIAL', failure_proof=proof)
                        if j['id'] in tool_exemptions:
                            row['tool_exemption'] = tool_exemptions[j['id']]
                    elif j['state'] in ('COMPLETE', 'CHILD_EXITED_HOLD'):
                        t = durable_wait(q, j)
                        if type(t['exit_code']) is int and t['exit_code'] == 0 and t['signal'] is None:
                            need(k not in selected, 'PN_NO_MULTIPLE_SUCCESSFUL_ATTEMPTS')
                            selected[k] = dict(job_id=j['id'], point_id=point_id,
                                replicate_id=k, attempt=j['attempt'],
                                claim=j['claim'], terminal_sha256=digest(t),
                                wait_observed=True, exit_code=0, signal=None,
                                state=j['state'])
                    chain.append(row)
                decisions[k] = decide_attempts(chain, original_limit=original_limit)
                need(k not in selected or chain[-1]['job_id'] == selected[k]['job_id'],
                     'PN_NO_LATER_ATTEMPT_AFTER_SUCCESS')
            terminal_candidate = all(k in selected or decisions[k]['terminal']
                                     for k in (1, 2, 3))
            basis = dict(queue_manifest_sha256=q.manifest, point_id=point_id,
                         original_jobs=jobs, partials=partials,
                         SYSTEM_allocations=allocations,
                         last_extra_grants=last_extra_grants,
                         tool_exemptions=tool_exemptions)
            authorization_refs = dict(last_extra_grants=dict(last_extra_grants),
                tool_waiver_sources={jid:
                    dict(original_authorization_sha256=x['original_authorization_sha256'])
                    if x.get('verified_exact_user_authorization') is True else
                    dict(original_public_projection_sha256=x['original_public_projection_sha256'],
                         public_code=x['public_code'])
                    for jid,x in tool_exemptions.items()})
            return dict(point_id=point_id, selected_jobs=selected,
                        selected_replicate_ids=sorted(selected),
                        replicates_complete_not_yet_audited=len(selected),
                        replicate_decisions=decisions,
                        terminal_candidate_not_yet_published=terminal_candidate,
                        original_state_sha256=digest(basis),
                        allowance_authorization_refs=authorization_refs,
                        failed_attempt_costs=failure_costs,
                        native_audit_required_for_every_selected=True,
                        original_wait_and_ledger_rows_unchanged=True)
        finally:
            q.mutex.release()
    finally:
        ledger.mutex.release()
