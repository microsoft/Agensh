"""Trusted metadata-only allowance decisions; never dispatches or changes a DB.

Raw attempt numbers are independent RNG identities, not consumed allowance.
Only the owner may supply certified original PARTIAL/cost and tool-fault proof.
This module deliberately has no log reader, model client, production path or
automatic retry loop. A RETRY decision is not a request replay or enqueue.
"""
from common import need, digest, sha

POLICY = 'USER_20261030_ORIGINAL_ALLOWANCE_PLUS_ONE_THEN_ACTUAL_N'
COST_FIELDS = ('native_request_count', 'native_aux_tokens',
               'unknown_aux_reservation_charge')
TOOL_CODES = frozenset(('AUX_SCOPE_NOT_CURRENT', 'FINAL_AUTHORITY_QUEUE_CLAIM'))
FAILED = frozenset(('PARTIAL_FAILED_REPLICATE_ATTEMPT',
                    'FAILED_EXIT_NOT_YET_PARTIAL'))
SUCCESS = 'COMPLETE_VALID_REPLICATE'
PENDING = frozenset(('UNKNOWN_TERMINAL_BINDING',
                     'EXIT0_AUDIT_PENDING_NOT_SCORE', 'UNKNOWN_DISPOSITION'))


def failure_classification(proof, *, tool_exemption=None):
    """No cost or exception type is evidence of a tool-fault cause.

    tool_exemption is an already verified public metadata projection, bound to
    THIS original claim, terminal, scope and child lifetime. Merely providing a
    code string, early timestamp, zero cost or Refused type is insufficient.
    Production callers must authenticate the projection against its original
    pinned receipt before passing it; this pure function is not that reader.
    """
    need(type(proof) is dict, 'PN_COST_PROOF_REQUIRED')
    for key in COST_FIELDS:
        need(type(proof.get(key)) is int and proof[key] >= 0,
             'PN_EXACT_NONNEGATIVE_COST_METADATA')
    for key in ('job_id', 'point_id', 'custody_proof_sha256'):
        sha(proof.get(key))
    kind = proof.get('proof_kind')
    need(kind in ('GENUINE_FAILED_WAIT', 'ORIGINAL_ORPHAN_PHYSICALLY_ENDED_NO_WAIT'),
         'PN_FAILED_CUSTODY_PROOF_KIND')
    if kind == 'GENUINE_FAILED_WAIT':
        need(proof.get('wait_observed') is True and
             proof.get('terminal_sha256') == proof['custody_proof_sha256'],
             'PN_GENUINE_WAIT_NOT_INVENTED')
    else:
        need(proof.get('wait_observed') is False and
             proof.get('terminal_sha256') is None and
             proof.get('exit_code') is None and proof.get('signal') is None,
             'PN_ORPHAN_NEVER_CLAIMS_A_WAIT_OR_KNOWN_EXIT')
    need(type(proof.get('scope')) is str and bool(proof['scope']) and
         type(proof.get('original_claim')) is str and
         bool(proof['original_claim']), 'PN_COST_ORIGINAL_SCOPE_AND_CLAIM')
    zero = all(proof[k] == 0 for k in COST_FIELDS)
    tool = False
    prior_waiver = False
    if tool_exemption is not None:
        x = tool_exemption
        need(type(x) is dict and all(x.get(k) == proof[k] for k in
             ('job_id', 'scope', 'original_claim', 'custody_proof_sha256')),
             'PN_EXEMPTION_SAME_ORIGINAL_CUSTODY')
        prior_waiver = x.get('verified_exact_user_authorization') is True
        if prior_waiver:
            sha(x.get('original_authorization_sha256'))
        else:
            need(kind == 'GENUINE_FAILED_WAIT' and
             x.get('public_code') in TOOL_CODES and
             x.get('same_scope') is True and
             x.get('within_child_lifetime') is True and
             x.get('verified_fixed_public_projection') is True and
             x.get('terminal_sha256') == proof['terminal_sha256'],
             'PN_MATCHING_CONFIRMED_TOOL_FAULT_REQUIRED')
            sha(x.get('original_public_projection_sha256'))
            tool = True
    basis = ('EXACT_PRIOR_USER_AUTHORIZED_FAILURE_WAIVER' if prior_waiver else
             'USER_CONFIRMED_SAME_SCOPE_TOOL_FAULT_EXEMPTION' if tool else
             'USER_ZERO_MODEL_ZERO_TOKEN_EXEMPTION' if zero else
             'NONEXEMPT_FAILURE_CAUSE_UNKNOWN')
    return dict(replacement_allowance_consumed=not (zero or tool or prior_waiver),
                cause='PUBLIC_WRAPPER_REFUSAL' if tool else 'UNKNOWN',
                zero_model_and_zero_token_proven=zero,
                confirmed_tool_fault=tool, basis=basis)


def decide_attempts(attempts, *, original_limit):
    """Plan one replicate using ALL original attempt identities, oldest first.

    original_limit is 3 for ordinary points, 4 only for an explicitly authorized
    natural point. The caller derives it from sealed policy, never a4 presence.
    ``last_extra`` is a persisted owner grant (including the three named a4s),
    not inferred from raw attempt==4. An exempt failure does not consume even
    this last grant; the next independent attempt retains that grant's status.
    """
    need(type(original_limit) is int and original_limit in (3, 4),
         'PN_ORIGINAL_AUTHORIZED_ALLOWANCE')
    need(type(attempts) is list and bool(attempts), 'PN_ALL_ATTEMPTS_REQUIRED')
    ids = set()
    point = attempts[0].get('point_id')
    replicate = attempts[0].get('replicate_id')
    sha(point)
    need(type(replicate) is int and replicate in (1, 2, 3), 'PN_REPLICATE_ID')
    consumed = 0
    extra_exempt = False
    extra_chain = False
    original_extra_grant = None
    for index, row in enumerate(attempts, 1):
        need(type(row) is dict and row.get('point_id') == point and
             row.get('replicate_id') == replicate and
             type(row.get('attempt')) is int and row['attempt'] == index,
             'PN_COMPLETE_CONTIGUOUS_ORIGINAL_ATTEMPT_CHAIN')
        expected = digest(dict(point=point, replicate=replicate,
                               **({'attempt': index} if index > 1 else {})))
        need(row.get('job_id') == expected and expected not in ids,
             'PN_ORIGINAL_JOB_RNG_IDENTITY')
        ids.add(expected)
        need(type(row.get('last_extra', False)) is bool,
             'PN_EXTRA_GRANT_BOOL')
        if row.get('last_extra', False):
            sha(row.get('last_extra_grant_sha256'))
            need(original_extra_grant is None or
                 original_extra_grant == row['last_extra_grant_sha256'],
                 'PN_EXEMPT_EXTRA_MUST_KEEP_SAME_GRANT_SHA')
            original_extra_grant = row['last_extra_grant_sha256']
        need(not extra_chain or row.get('last_extra', False),
             'PN_EXEMPT_EXTRA_MUST_KEEP_ORIGINAL_LAST_EXTRA_GRANT')
        state = row.get('state')
        if state != 'PARTIAL':
            need(index == len(attempts), 'PN_NO_ATTEMPTS_AFTER_UNDISPOSED_OR_SUCCESS')
            need(state in ('QUEUED', 'CLAIMED', 'RUNNING', 'CUSTODY_UNKNOWN',
                           'CHILD_EXITED_HOLD', 'COMPLETE'), 'PN_KNOWN_JOB_STATE')
            return dict(policy=POLICY, action='SUCCESS_REQUIRES_NATIVE_AUDIT'
                        if state == 'COMPLETE' else 'WAIT_ORIGINAL_ATTEMPT',
                        consumed_failures=consumed, original_limit=original_limit,
                        next_attempt=None, terminal=False,
                        original_last_extra_grant_sha256=original_extra_grant)
        proof = row.get('failure_proof')
        need(type(proof) is dict and proof.get('job_id') == expected and
             proof.get('point_id') == point, 'PN_PARTIAL_COST_SAME_JOB')
        classification = failure_classification(
            proof, tool_exemption=row.get('tool_exemption'))
        consumes = classification['replacement_allowance_consumed']
        if consumes:
            consumed += 1
        extra_chain = extra_chain or row.get('last_extra', False)
        exhausted = consumes and (row.get('last_extra', False) or
                                   consumed >= original_limit + 1)
        need(not exhausted or index == len(attempts),
             'PN_NO_AUTOMATIC_ATTEMPT_AFTER_LAST_EXTRA_FAILURE')
        if index == len(attempts):
            if exhausted:
                action = 'TERMINAL_ALLOWANCE_EXHAUSTED'
                nxt = None
            else:
                extra_exempt = extra_chain and not consumes
                action = ('NEW_INDEPENDENT_LAST_EXTRA'
                          if extra_exempt or consumed >= original_limit
                          else 'NEW_INDEPENDENT_ORIGINAL_ALLOWANCE')
                nxt = index + 1
            return dict(policy=POLICY, action=action, next_attempt=nxt,
                        terminal=exhausted, original_limit=original_limit,
                        consumed_failures=consumed,
                        exempt_failures=index-consumed,
                        next_is_last_extra=action == 'NEW_INDEPENDENT_LAST_EXTRA',
                        classification=classification,
                        original_last_extra_grant_sha256=original_extra_grant,
                        raw_attempt_is_not_consumed_allowance=True)


def terminal_window(rows, *, start_ns, end_ns):
    """Preserve the existing 12:14 distinct physical-terminal attempt units.

    Owner/extractor supplies only original CHILD_TERMINAL-bound metadata.
    Never derives a terminal from QUEUED/RUNNING, row mtime or missing samples.
    Exit0 HOLD stays pending, not successful. Duplicate identical observations
    are deduplicated; conflicting observations are refused, never best-picked.
    """
    need(type(start_ns) is type(end_ns) is int and 0 <= start_ns <= end_ns,
         'PN_EXACT_TERMINAL_WINDOW')
    seen = {}
    counts = {}
    for row in rows:
        need(type(row) is dict and type(row.get('first_ns')) is int,
             'PN_ORIGINAL_TERMINAL_EVENT_TIME')
        sha(row.get('queue_manifest_sha256'))
        sha(row.get('job_id'))
        outcome = row.get('outcome')
        need(outcome in FAILED | PENDING | {SUCCESS}, 'PN_KNOWN_TERMINAL_OUTCOME')
        key = (row['queue_manifest_sha256'], row['job_id'])
        if key in seen:
            need(seen[key] == row, 'PN_CONFLICTING_TERMINAL_OBSERVATION')
            continue
        seen[key] = row
        if not start_ns <= row['first_ns'] <= end_ns:
            continue
        counts[outcome] = counts.get(outcome, 0) + 1
    failed = sum(counts.get(k, 0) for k in FAILED)
    succeeded = counts.get(SUCCESS, 0)
    pending = sum(counts.get(k, 0) for k in PENDING)
    denominator = failed + succeeded
    return dict(start_ns=start_ns, end_ns=end_ns, counts=counts,
                known_failed=failed, complete_valid=succeeded,
                pending_or_unknown=pending, decided_denominator=denominator,
                decided_failure_rate=failed/denominator if denominator else None,
                lower_bound_if_all_pending_succeed=
                    failed/(denominator+pending) if denominator+pending else None,
                systemic_rep_failure_gt30_percent=bool(
                    denominator and failed * 10 > denominator * 3),
                units='distinct physical-terminal replicate attempt; not model request; each job counted once',
                existing_model_and_billing_hard_stops_unchanged=True)
