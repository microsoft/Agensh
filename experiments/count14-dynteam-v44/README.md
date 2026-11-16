# count14 dynamic-team orchestration — frozen V44 review export

This is a **source-reading bundle**, not an installable package, a portable launch
recipe, or evidence that the experiment has completed. It projects the frozen
V44 source used for the N33 run into readable functional directories. No live
process, model, task, evaluator, or experiment data was accessed to make it.
Do not execute the experiment entry points in this tree as a smoke test.

**Configuration:** gateway addresses and provider-key locations are not in the code; they come
from environment variables. See [`CONFIGURATION.md`](CONFIGURATION.md) and
[`count14.env.example`](count14.env.example).

## Experiment and invariants

The count14 experiment compares **DYNTEAM** and **DYNTEAM_RACING**, with three
paired blocks (**b1–b3**) per arm: six independently budgeted trajectories. Each
trajectory has a **100 million SEARCH-token** budget and checkpoints at
**10M, 20M, 50M, and 100M**. Every model-using role, including RACING helpers and
an authorized setup-completion turn, is charged. The protocol is **K3 v2.1**:
three separately tracked finalization children per checkpoint, isolated from
SEARCH and with separately scoped AUX accounting. Official evaluation feedback
must not flow back into SEARCH.

Both arms start with the original worker/checker/tester roles and retain native
dynamic membership rather than equating a request cap with a lifetime role-birth
limit. The equal SEARCH cap is **13 per trajectory** (78 over six trajectories);
the contract also defines 12 FINAL jobs, 16 AUX slots and two reserved SYSTEM
probe slots. These are subject to the overriding **96 physical FP8 in-flight**
aggregate cap; the individual limits are not permission to exceed it.

The paired seeds are b1=4287909351, b2=1636023914, b3=2619738241. These are
configuration values, not task or result data. See `contracts/production.json`
for the frozen declarative design; its historical readiness/authorization flags
are not a current deployment-status report.

## Upstream baselines and patch provenance

The two source baselines are from other branches/repositories, **not commits
contained in microsoft/Agensh**:

| Source branch | Baseline commit | Purpose |
| --- | --- | --- |
| `zhihao/beta_dev` | `70e2ca54c078597e3314755064d2ef1a83344c8e` | Native dynamic-team agent/router orchestration |
| `moa/racing` | `21a0413e3262cebd5c6ac314974710937b9741b0` | RACING loop integrated through experiment-specific public-tool adapters |

* `patches/beta_agent_and_router.patch` contains the guarded-agent changes,
  added bridge helpers, and changed router TypeScript/clock sources relative to
  the delivered beta snapshot. Unchanged upstream files are not vendored.
* `patches/selected_sdk_restore_overlay.patch` contains only the **selected**
  prospective SDK-overlay changes, relative to the pinned guarded agent and
  compiled clock-router snapshots. It is a distinct, later phase/domain, not a
  second arbitrary historical version of the active router. The JavaScript
  baseline is a delivered compiled snapshot, **not** a git source-tree diff.
  The source still marks full cold-owner restoration as unqualified.
* The frozen input has no baseline git objects. Snapshot hashes and exact diff
  endpoints are recorded in `MAPPING.json`; these patches are **not claimed to
  be independently git-verified** against the named commits. They are review
  artifacts, not instructions to apply both blindly to this repository.
* The RACING merge declaration identifies revision retention in `nloop/judge.py`
  as its upstream change. An unmodified judge blob from the RACING baseline is
  absent from the allowed frozen input. Consequently **no RACING baseline patch
  is invented**. The upstream `nloop` tree and prompts are omitted; our separately
  pinned orchestration/tool adapters remain available for review. Completing an
  independently verified RACING diff requires the actual baseline outside this
  export task's read-only input scope.

## Architecture and directory guide

| Directory | Responsibility |
| --- | --- |
| `adapter/` | Dynamic membership, native backend layout, initial owner/bootstrap and immutable role/session exports |
| `runtime/` | Six-track owner composition, session/control inbox, router hooks, source bindings, continuing-service contracts and retirement |
| `relay/` | Scientific HTTP relay, shared ledger/budget enforcement, dispositions and GLM gateway binding |
| `admission/` | Fresh resource/health observations, promise accounting, allocation and active-clock/idle controls |
| `finalization_k3/` | Cut/checkpoint controller, allowance and queue authorization, subprocess launch/attach/reap/audit, terminal publication |
| `framework/` | Reused experiment framework orchestration and fresh-start/expansion support; not the vendored beta or RACING tree |
| `racing_integration/` | Our host/guest integration, public-tool scope checks, setup completion and original game-execution custody |
| `contracts/` | Declarative production/model policies and source-scope compilers, not runtime evidence |
| `ops_tools/` | Pinned launch/host helpers and read-only reporting/tester-binding implementations; no observations or logs |
| `patches/` | Changes to external beta-derived agent/router source; no wholesale vendor trees |
| `tools/` | Offline integrity and syntax-only verification utility |

Useful starting points are `runtime/owner/native_formal_cohort.py`,
`relay/core/original_relay_core.py`, `relay/financial/native_scientific_http.py`,
`finalization_k3/checkpoints/native_dynamic_checkpoint.py` and
`finalization_k3/checkpoints/smoke_checkpoint_final_controller.py`.
Names containing `smoke`, `cold`, or historical numbers are frozen module names,
not a claim that the module is merely a test or that its entry point is safe to
run. Directory names are normalized; module contents and their import names are
intentionally not rewritten.

### Request and control flow

1. **Native role/session → local relay → GLM gateway.** Router/agent hooks bind a
   native session to a trajectory and control route. The relay authenticates
   local peers and forwards permitted scientific requests to the configured GLM
   endpoint. Provider credentials remain external file/environment references;
   no credential files are present here.
2. **Ledger and budget.** Reservation, send and settlement are explicit states.
   Reported usage is settled; an uncertain physical/usage outcome is retained as
   UNKNOWN, never silently zeroed or replayed. The conservative total context
   bound is 524,288 tokens, **input plus output**, not an independent output
   allowance. An absent client output limit stays absent on the wire; an
   explicit client limit passes through. SEARCH, AUX and SYSTEM remain distinct
   accounting domains.
3. **Admission.** The original admission path uses ledger/physical counts, equal
   per-track/global caps, fresh health/performance observations, RAM and storage
   promises. Missing/invalid health is not success. Health may reopen admission
   automatically when a valid snapshot is fresh (60-second bound); it does not
   bypass any other guard. Ledger-before-queue lock ordering is preserved.
4. **Checkpoint cut.** New admissions for that trajectory stop; existing native
   physical tails and membership/session barriers are handled by the original
   checkpoint machinery. The cut captures an immutable search/membership state,
   then publishes authorized final-queue work. A SEARCH budget threshold is not
   a reason to cancel or replay an already sent physical request.
5. **K3 finalization.** The queue authorizes three children, records each launch
   and attach, waits/reaps the original child and audits its terminal outcome.
   First-failure locations remain public metadata, with per-track/per-point
   isolation so another trajectory can continue. Successful nonterminal cuts
   restore that trajectory's original SEARCH path before its next cut. Final
   retirement is stricter than a normal cut and waits for physical custody.
6. **RACING setup and completion.** RACING has seven players and one background
   role in the contract, with an active-clock no-progress trigger and public-tool
   validation. Integration preserves original session/turn identity. A narrowly
   authorized missing-setup completion can run **at most once**, with a durable
   used bit and the same SEARCH charges, cap and UNKNOWN accounting. It is not a
   general retry, new prompt, private reference or official evaluator verdict.

## Fixes incorporated during N25–N33 development

These are source changes retained by V44, not claims that every path has passed
an end-to-end live run. Each row is **problem → change → current review file**.
The N25–N33 identifiers name successive experiment instances, not public API
versions. Source registers were read for this summary but are not exported as
runtime/build evidence.

* Provider selection was applied outside a captured startup barrier → bind the selected provider before the unchanged barrier/sealer → `runtime/continuation_contracts/normal_cold_sealer_cold.py` and `relay/providers/provider_pr1_selection.py`.
* Zero-model preparation exposed only a generic wrapper → retain the first owned failure location and cached public diagnostic, without changing native operations/timeouts → `adapter/runtime/native_cold_owner.py`, `runtime/session_control/native_session_control.py` and `runtime/router/native-racing-phase-port.mjs`.
* Storage promises could subtract the new batch twice after activation → keep the original pre-activation formula through ACTIVATE and use the explicit runtime phase afterward, with no future-cleanup credit → `admission/resources/native_cohort_resources.py`, `admission/resources/native_resource_producer.py` and `admission/resources/native_resource_sampler.py`.
* Total context length could be mistaken for an output cap → reserve the total input-plus-output bound, omit absent wire limits and preserve explicit client limits across all domains → `relay/financial/scientific_relay.py`, `relay/financial/native_scientific_http.py` and `finalization_k3/checkpoints/smoke_checkpoint_final_runtime.py`.
* Early sanity incorrectly treated a short-output median as disqualifying → remove that median rule while preserving empty/no-claim/no-tool and metadata-truth checks → `ops_tools/reporting/formal_early_sanity.py`.
* Native END could look like a reservable/sendable request or leak a held lease → explicit no-send END hold, pre-park/session ownership and duplicate-archive handling → `adapter/membership/dynamic_role_gate.py`, `runtime/session_control/native_bridge_owner.py` and `relay/financial/native_scientific_http.py`.
* Checkpoint replacement could lose the pre-park/session barrier or repeated tester cycle → carry original membership/session state through capture and restoration → `finalization_k3/checkpoints/native_dynamic_checkpoint.py` and `adapter/runtime/native_dynamic_writer.py`.
* First background end-turn could precede complete RACING setup → permit only the original, exactly guarded, durable at-most-once setup-completion turn, charged to SEARCH → `runtime/router/native-racing-phase-port.mjs` and `racing_integration/host/native_racing_phase_client.py`.
* Transient ledger try-lock contention could permanently fail FINAL dispatch → normal blocking acquisition with ledger-before-queue ordering → `finalization_k3/allowance_native/allowance_control.py`, `finalization_k3/allowance_queue_proposal/queue_control.py` and `adapter/runtime/native_sdk_startup_epochs.py`.
* One dispatch/controller error could mask its first cause or stop unrelated tracks → retain the first public exception type/location and isolate per-track polling, including controller-finally behavior → `finalization_k3/framework/native_final_dispatch.py`, `runtime/owner/native_formal_cohort.py` and `finalization_k3/checkpoints/smoke_checkpoint_final_controller.py`.
* Retirement's wait-source exception could stop all six-track polling → isolate that wait-source failure while allowing the poll loop to continue → `runtime/retirement/formal_cohort_retirement.py`.
* A base-class per-point exception fix was bypassed by the production subclass → apply point-isolated snapshot/producer handling to the actual `NaturalCompositeTerminalSource` override → `finalization_k3/natural_point/formal_natural_terminal.py` (with shared policy in `finalization_k3/nlt3/formal_nlt3_source.py`).
* SESSION_READY could expire in the inbox before execution during startup or the paid-unsent path → allow at most three identical metadata reproposals **only after exact EXPIRED_UNSTARTED proof**, never for RUNNING/SENT/UNKNOWN → `runtime/session_control/native_control_inbox.py`, `runtime/session_control/native_session_control.py`, `runtime/router/router-session-hook.mjs` and `runtime/router/native-racing-phase-port.mjs`.

The intervening host unattended-upgrade/daemon restart was an infrastructure
incident, not repaired by adding experiment daemon auto-healing. Host upgrade
protection is an operations action and is **not** shipped as a source hotfix or
an instruction to change the reviewer's host.

## Known limitations and non-goals

* There is **no qualified paid cold-continuation entry point**. Pinned prototype,
  verifier and restoration-contract source does not constitute permission or a
  proven route to reconstruct a paid owner. In particular, the prospective SDK
  patch is not evidence that whole-owner cold restoration works.
* Gateway inference wiring was migrated, but resource health still depends on
  the **older METRICS endpoint**. An unavailable/invalid snapshot can keep the
  original owner in health hold; a fresh valid observation can reopen the same
  admission path. This bundle neither fixes that endpoint nor runs a probe.
* SYSTEM probes marked **UNPROVEN_PHYSICAL_UNKNOWN** can block eventual final
  retirement in its wait/closing state. They are not zero-usage terminal records;
  normal checkpoint cuts and final retirement have different custody predicates.
  No same-owner reconciliation tool is supplied here.
* A resource/health hold does not itself pause every native router watchdog.
  The original silence-watchdog interaction remains a risk, not a proven failure
  or a new timeout exemption.
* Runtime qualification, data/evaluator permissions, environment images, secret
  provisioning, upstream licenses and independent baseline availability must be
  reviewed separately. No qualification matrix, model call, service import,
  container command, or experiment entry point was run for this export.
* This source bundle has **no experiment results** and makes no 100M, first-cut,
  K3 completion or full-retirement claim.

## Exact relationship to frozen V44

**Publication edits.** 67 files differ from the frozen V44 bytes on purpose: hard-coded
model-gateway URLs, provider-key paths, testbed scratch paths, host name, boot ID and filesystem
UUID were replaced by environment lookups (see
[`CONFIGURATION.md`](CONFIGURATION.md)). Each such Python file gains an `import os as _count14_os` line plus one constant line per setting it
uses, so line numbers quoted elsewhere in this README for those files are shifted. The original and
published SHA-256 of every edited file are in [`CONFIGURED_FILES.json`](CONFIGURED_FILES.json);
`tools/verify_mapping.py` reports exactly these files as mismatches against the frozen source.
All other files are byte-identical to the frozen source.

The read-only input is the `PAYLOAD` of
`MSG276_FORMAL_N33_SESSION_READY_WHOLE_V44`, whose full local pathname is in
`MAPPING.json`. Selection starts from its ordered `SOURCE_IMPORT_LAYOUT` and the
identical effective framework import registry, not from the apparent age of a
directory name. The first matching immediate module is selected once. Pinned
FINAL-child, observer, guest, provider-child and prospective SDK asset domains
are tracked separately where the frozen source explicitly uses a different
process/path namespace. Nested assets are taken only from effective contributing
roots, with the selected SDK overlay and explicit public-router path winning
over historical alternatives.

* Input manifest SHA256: `527d9e3264c08381b412659855887722314d58367dc23d3f33a512aea7267021`.
* Ordered source-layout SHA256: `45d6234c3c0a4ba684c410518772c3ef63a504bf062e837c1915f325fd0ae1f0`.
* Effective import-registry SHA256: `2ed04b26e0c5a8a8e1e2539eb56260eaf2efd964b8f3f024413bc935bb4225e4`.
* Frozen CODE contains 12,009 members; 696 immediate source-module names are resolved before exclusion.
* This export has 525 verbatim source/config files and two generated unified patches; 135 byte-identical selected source aliases share one stored copy.

`MAPPING.json` maps **every copied review path** to its frozen `CODE` relative
path, byte count and SHA256. `equivalent_sources` preserves other selected
same-byte origins. Patch entries instead identify every before/after frozen path
and SHA256, plus the patch's own hash. `tools/` and this README are newly authored
export utilities/documentation, not represented as frozen runtime source; the
mapping itself is generated provenance rather than a copied evidence file.

No copied source body was edited, including imports, pin constants, internal
URLs, root labels or seed values. Functional relocation and content deduplication
therefore intentionally mean **this is not an importable deployment tree**.
The owner framework and FINAL child's differing files are distinct pinned
domains, not two arbitrary historical choices. Baseline/context lines that also
appear inside a patch are diff context, not another vendored implementation.

### Offline integrity and syntax check

```sh
python3 tools/verify_mapping.py
# Optional, on the export machine only, compare all allowed source endpoints:
python3 tools/verify_mapping.py --payload /path/to/frozen/PAYLOAD
```

The verifier parses Python in memory (no imports or bytecode), runs only Node's
and Bash's syntax parsers for copied JavaScript/shell source, parses the two
static JSON policies, and checks hashes/deduplication. With `--payload`, it also
regenerates patch bytes in memory and parses their Python/JavaScript endpoints.
TypeScript patch endpoints are not typechecked, bundled or executed. This is
**not a runtime or qualification test**. The exporter itself defaults to dry-run;
`--write` writes only to this export directory. An independent secret scan is
still required before a draft PR is pushed.

## Excluded

* The entire vendored `upstream-70e2ca54` tree, complete RACING source trees,
  upstream `nloop`, prompts, and unused/shadowed delivery copies; only the
  described modifications and our separately pinned orchestration are retained.
* All task/source samples, candidates, model outputs, private contexts, state
  pickles, evaluator-private content, credential files, database/ledger/queue
  data, runtime PUBLIC observations, retained histories, build evidence,
  qualification matrices, archives and logs. A filename such as
  `private_sampler_selection.py` denotes orchestration code, not private sample
  contents. Only two newly located declarative JSON contracts are copied.
* `retained_formal_frozen_snapshot_v1.py` — explicitly forbidden embedded retired
  snapshot. All manifest-listed copies were excluded **without opening or
  decoding their bodies**.
* `orphan_storage_retirement_reader.py` — embeds a literal data table larger than
  4 KiB; the whole source file is omitted rather than extracting its data.
* Test/qualification/fixture/probe entry points (including `own-*.mjs`) and
  historical resume commands. `own_held_stage_pair_v3.py` is retained as the
  selected source-verification dependency of the continuing-service code, not
  executed or presented as a paid-continuation route.

The explicit selected-file exclusion records and general policy are in
`MAPPING.json`. Omitted data, credentials and opaque blobs are not reconstructed.

## Endpoint inventory

These are source/configuration dependencies, **not recommendations or live
availability claims**. The external model-gateway addresses and the provider-key
locations are **not hard-coded** in this export: they are read from environment
variables documented in [`CONFIGURATION.md`](CONFIGURATION.md) (template:
[`count14.env.example`](count14.env.example)). No gateway dashboard URL is included.
The entries below are loopback or in-cluster service names only. Each location below
refers to this review tree; locations inside patches include baseline/context or
removed lines as well as additions. Generated provenance in `MAPPING.json` is
not a runtime configuration and is not expanded into this inventory.

| URL literal/prefix | Every occurrence (review file:line) |
| --- | --- |
| `http://127.0.0.1:` | `adapter/runtime/smoke_bootstrap_task_ports.py:205`; `adapter/runtime/smoke_bootstrap_task_ports.py:206`; `framework/native/native_dry_start_probe.py:288` |
| `http://127.0.0.1:$EDGE_MM_PORT` | `adapter/runtime/smoke_bootstrap_task_launch.py:37`; `admission/idle_watchdog/native_idle_source.py:61` |
| `http://127.0.0.1:${COUNT14_GIT_FRONT_PORT` | `framework/native/native_worker_launch.py:33` |
| `http://127.0.0.1:12578` | `framework/startup/prepare_fresh48.py:84` |
| `http://127.0.0.1:12578/v1` | `framework/startup/fresh48_preledger.py:19`; `framework/startup/fresh48_zero.py:112`; `framework/startup/prepare_fresh48.py:83`; `framework/startup/run_fresh48.py:65` |
| `http://127.0.0.1:4181/{record[` | `ops_tools/host/task-host.py:262` |
| `http://127.0.0.1:8650/identities/` | `ops_tools/launch/count14_spawn_loop.sh:143` |
| `http://127.0.0.1:{port` | `framework/native/native_worker_launch.py:108`; `framework/native/native_worker_launch.py:135` |
| `http://127\.0\.0\.1:[1-9][0-9]{0,4}/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.git/` | `framework/native/native_shell_context.py:20` |
| `http://board-service:8660` | `ops_tools/host/task-host.py:340` |
| `http://gitea:3000` | `finalization_k3/child_framework/bootstrap-scientific.sh:7`; `ops_tools/host/task-host.py:340`; `racing_integration/host/smoke_racing_tools_game_manager.py:229`; `racing_integration/host/smoke_racing_tools_publication.py:76` |
| `http://mattermost:8065` | `ops_tools/host/task-host.py:340` |
| `http://secret-service:8650` | `ops_tools/host/task-host.py:340` |
| `http://{address[0]}:{address[1]}/v1` | `runtime/source_bindings/http_runtime_source_control.py:181` |
| `http://{gateway}:{port}/v1` | `ops_tools/host/task-host.py:244` |
| `http://{host}:{port}/v1` | `adapter/runtime/native_cold_exports.py:227`; `adapter/runtime/native_host_environment.py:180` |

## Testbed host and path settings

The original testbed's scratch mounts, host name, boot ID and scratch-filesystem UUID are **not
hard-coded**: they are read from `COUNT14_SCRATCH_ROOT`, `COUNT14_SCRATCH1_ROOT`, `COUNT14_HOSTNAME`,
`COUNT14_HOST_BOOT_ID`, `COUNT14_RETIRED_OWNER_BOOT_ID` and `COUNT14_SCRATCH_FS_UUID`
(see [`CONFIGURATION.md`](CONFIGURATION.md)). Experiment-root directory names (for example the
per-run root labels under the scratch root) remain as relative names below that root. The three
paired seeds are experiment configuration and stay in the contract. Every edited file is listed in
[`CONFIGURED_FILES.json`](CONFIGURED_FILES.json).

### External credential-file references (paths only, no file contents)

These locations refer to key/token/phase-secret files or their path variables.
Only the orchestration text is included; none of those files was opened or
copied for this export. Normal authentication-construction code is not an
embedded bearer credential. A literal local-relay placeholder is not a provider
key and cannot authenticate to the provider.

| Review file | Lines |
| --- | --- |
| `adapter/runtime/native_cold_exports.py` | 213, 217, 218 |
| `finalization_k3/child_framework/bootstrap-scientific.sh` | 23, 191, 192, 460, 464, 465, 520, 524, 526, 571, 572 |
| `framework/extensions/aggregate_install.py` | 128 |
| `framework/extensions/glm_session_header.py` | 8 |
| `framework/native/baseline_micro_driver.py` | 81 |
| `framework/native/native_dry_start_probe.py` | 51, 289, 302 |
| `framework/native/native_scientific_bootstrap.py` | 18, 27 |
| `framework/native/native_worker_launch.py` | 32, 108, 135 |
| `framework/native/run_native_scientific6.py` | 152, 222 |
| `framework/startup/fresh48_configuration.py` | 39, 42, 52 |
| `framework/startup/fresh48_hooks.py` | 94, 95 |
| `framework/startup/prepare_fresh48.py` | 86, 87 |
| `framework/startup/run_fresh48_final_child.py` | 25 |
| `racing_integration/host/smoke_racing_tools_game_manager.py` | 233 |
| `relay/financial/feasibility_relay.py` | 250 |
| `runtime/composition/newroot_native_exact_metadata_cold/native_racing_runtime_metadata.py` | 49 |
| `runtime/source_bindings/native_control_whitelist_source.py` | 455 |
