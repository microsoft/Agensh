# ADR-001: Validate portable peer coordination before infrastructure adoption

Status: Proposed
Date: 2026-10-25
Research baseline: `0468a3e6a58b51dc2b84871fcaa0df22b0d1033e`

TL;DR: Preserve Agensh's peer coordination semantics when investigating integration
with an existing orchestrator, agent SDK or AWS environment. Start with the
offline shared-context probe and a measured, bounded experiment. This proposal
does not change the released runtime, add cloud infrastructure or claim new
benchmark results. Service recovery, authentication and model-backed comparisons
remain unqualified; the next action is maintainer feedback on this experiment.

## Context and benefits

Use this proposal when learning from Agensh to improve an existing agent stack,
or when considering alternative infrastructure behind the cooperation loop.
The relevant design is versioned shared work, asynchronous messages and concise
reusable context, rather than a particular cloud service.

The [README](../../README.md) reports that mean final canonical test-pass rate
across five ProgramBench tasks rose from 19.31% with one worker to 28.78% with
128 workers under a six-hour budget. The [report](../../agensh.pdf), Sections
2.2, 3 and Appendices B/C, describes peer specialization, negotiated integration
protocols, event-driven sessions and staggered worker activation. These results
support investigating quality and latency benefits. They do not establish equal
token-budget or equal-cost efficiency, production reliability, or portability
to a different model, task or cloud.

| Mechanism | Expected benefit | Evidence needed in another stack |
|---|---|---|
| Typed shared findings and counterexamples | Reuse discoveries and avoid repeating failed approaches | Fewer repeated investigations, accurate provenance and unchanged task quality |
| Advisory claims and peer negotiation | Flexible specialization without a task-planning bottleneck | Overlap resolution, bounded abandoned work and useful progress under worker loss |
| Durable asynchronous events plus serialized worker turns | Continue peer work without global barriers | Restart/redelivery correctness and bounded queues under representative load |

Git provenance and peer review make integration inspectable. They do not replace
the host project's independent tests, protected merge policy or release authority.

## Decision proposed

Keep the current implementation as the reference. Explore a thin adapter around
existing coordination interfaces before building another orchestration engine.
An existing Relay-style orchestrator can provide task lifecycle, budgets and
authority while its agent SDK provides model/tool execution. Peer workers can
still discover work, exchange findings and negotiate integration inside those
bounds. This is a hybrid experiment, not a claim to reproduce fully decentralized
allocation or the paper's results.

Separate worker-reported observations, admitted context and independently executed
validation. A board checkpoint records the candidate's textual evidence state.
It must not alone authorize a merge, infrastructure action or release. Preserve
the host's actual reviewed-source, artifact and validation receipt checks.

## Offline POC and observed boundaries

Run from a fixed checkout using Python 3.11 or newer:

```sh
python3 tools/coordination_probe.py
```

The probe imports the actual `SharedLessons` and `verify_note` implementations.
It uses synthetic task labels and a controlled clock; it starts no database,
HTTP service, model, agent container or AWS resource. Its nine assertions check:

- Concurrent same-label claims remain visible for both authors. Claims are
  advisory coordination entries, not exclusive ownership locks.
- Expired claims disappear from the live view but remain in the retained
  in-memory history. This does not establish MySQL restart recovery.
- Three identical facts become one visible gist with all three authors; the
  lifecycle export records three writes and two reads. This demonstrates context
  compaction and usage accounting, not a token or quality improvement.
- A revised patch replaces that author's prior candidate for the same work label.
- An author's matching failure invalidates its candidate. A different author's
  failure remains visible but does not automatically invalidate that candidate;
  peer counterexamples need reconciliation.
- Missing, placeholder or truncated evidence is rejected. A claimed pass for a
  nonexistent command is admitted and classified as a checkpoint because the
  verifier checks text rather than executing tests.

Good output is nine executed cases, zero failures/errors/skips and exit status
zero. A missing case or changed behavior requires investigating the new source
before carrying these conclusions forward. JSON on stdout records the boundary;
the test diagnostics are on stderr.

## AWS mapping to investigate

Use the existing application's infrastructure owner and package registry. The
following are alternatives for an experiment, not new deployment declarations:

| Existing responsibility | Candidate AWS integration | Invariants to retain |
|---|---|---|
| Long-lived worker and persistent ACP session | ECS task with isolated workspace/session storage | Per-worker turn serialization, cancellation, deadline and least-privilege execution |
| Router durable events | Existing durable queue; an SQS-backed adapter if needed | Stable event identity, ordering scope, bounded retry and idempotent processing under redelivery |
| Board persistence and context view | Current MySQL on RDS, or a separately qualified data-store adapter | Membership, expiry, provenance, retained history and cursor behavior |
| Versioned workspace and peer review | Existing Git host rather than another Git service | Isolated branches, exact reviewed commit, conflict handling and protected merge gates |
| Run archives and validation artifacts | S3 immutable/versioned objects | Content digests, source identity, bounded access and independent validation |
| Worker credentials and model route | Existing runtime credential broker, IAM and secret management | No agent-held broad cloud privilege; no credentials in gists or artifacts |

SQS delivery semantics do not by themselves serialize an ACP session or make
side effects exactly once. DynamoDB TTL would not replace live expiry checks or
exclusive fencing. Short-lived Lambda functions are candidates for bounded event
or artifact processing, not an assumed replacement for long-lived agent sessions.

## Alternatives

Keep the existing stack unchanged and reuse only concise typed findings. This
has the lowest operational cost and provides a useful comparison baseline.
Adopt the reference Compose stack for a research cohort. This preserves more
reference behavior but adds infrastructure and does not prove AWS integration.
Implement every coordination component anew. This offers flexibility but adds
the largest maintenance and semantic drift cost; defer it until a measured
adapter limitation justifies the work.

## Validation before adoption

Compare the existing stack, shared-context-only integration and a bounded peer
cohort on the same frozen tasks, source, model settings and evaluator revision.
Record seeds, repetitions, independently held oracles, executed/skipped cases,
canonical task quality, time to useful result, total tokens/cost, worker-hours,
duplicate/conflicting work and human integration effort.

Run both equal-wall-time and equal-total-work/cost comparisons. Declare the
adoption threshold before running the cohort, and retain failed attempts.
The offline probe establishes semantics only; it cannot choose that threshold
or demonstrate model-backed benefits.

Inject worker loss, router restart, redelivery, expired claims, concurrent edits,
peer counterexamples and changed source after verification. Require preserved
authority and no lost required validation. Service-backed tests must also cover
membership, credential boundaries, queue saturation and artifact access.

## Risks and responses

Advisory claims can overlap. Keep peer negotiation for research, and use existing
host task ownership/fencing for exclusive side effects. If a new exclusive claim
adapter is proposed, test expiry, stale-owner writes and atomic acquisition.

Textual checkpoint status can be mistaken for verified execution. Keep context
and release evidence separate; bind host validation to exact source and outputs.
Peer failures must reach the accountable author/integrator before adoption.

Retries can repeat work and cloud costs can exceed a fixed latency budget. Use
the host's budgets, cancellation and idempotency controls; report total work and
cost alongside quality and latency.

Alternative infrastructure can drift from the reference. Pin interface/source
versions, retain the probe and qualify each changed persistence or delivery
boundary before extending scale.

## Open questions for maintainers

Would a small portability/conformance probe be useful upstream? Which coordination
interfaces should be treated as supported integration seams? Should checkpoint
text be described differently for integrations with independent validation?
Are maintainers interested in an optional infrastructure-adapter experiment,
or should that work remain in a downstream integration repository?
