"""Pure PUBLIC contract compiler; no runtime/ledger/host mutation.

This instantiates the paired seeds, native slot catalogue and v2 invariants.
It deliberately cannot assert runtime_ready before actual owner/whole-roster
checkpoint/K3 wiring and the unique OPS the production host smoke have been qualified.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from copy import deepcopy
from dynteam_metadata import COMMIT, catalogue, digest, need

SEEDS = (4287909351, 1636023914, 2619738241)
ROOT = (_C14_SCRATCH + "/count14-dynteam-70e2ca54-20261105")
SMOKE_ROOT = (_C14_SCRATCH + "/count14-dynteam-70e2ca54-smoke-20261105")
EVAL_SOCKET = ("unix://" + _C14_SCRATCH + "/count14-eval-docker-20261030/docker.sock")


def compile_contract(design, source_audit, *, mode):
    need(mode in ("production", "smoke"), "DYNTEAM_EXPLICIT_MODE")
    need(design["schema"] == "count14-dynteam-preregistered-adaptation-design-v2" and
         design["source_commit"] == source_audit["source_commit"] == COMMIT,
         "DYNTEAM_DESIGN_SOURCE_LOCK")
    need(design["selected_native_worker_slots"] == 32 and
         design["total_native_model_role_catalogue"] == 34, "DYNTEAM_CANONICAL_LAUNCHER32")
    need(tuple((r["block"], r["search_seed"], r["paired_v2_seed"]) for r in design["trajectories"]) ==
         tuple((b, s, s) for b, s in enumerate(SEEDS, 1)), "DYNTEAM_PAIRED_ORIGINAL_SEEDS")
    need(design["search_budget_tokens_per_trajectory"] == 100000000 and
         design["checkpoints_tokens"] == [10000000, 20000000, 50000000, 100000000] and
         design["finalization"] == {"K": 3, "official_test_feedback_to_SEARCH": False,
                                    "protocol": "v2.1", "separate_AUX_accounting": True},
         "DYNTEAM_UNCHANGED_FORMAL_BUDGET_K3")
    need(design["root"] == ROOT and design["smoke_root"] == SMOKE_ROOT,
         "DYNTEAM_EXACT_NEW_SCRATCH_SCOPES")
    limits = design["external_FP8_limits"]
    need(limits["per_trajectory_inflight_upper"] == 32 and
         limits["all_own_relay_roots_inflight_upper"] == 96 and
         limits["FINAL_global_upper"] == 12 and
         limits["global_gateway_load_not_admission_counter"] is True and
         limits["independent_SYSTEM_probe_slot_reserved"] is True, "DYNTEAM_ORIGINAL_RESOURCE_LIMITS")
    need(not source_audit["working_copy_missing_orchestration_paths"], "DYNTEAM_COMPLETE_PINNED_ORCHESTRATION")
    root = ROOT if mode == "production" else SMOKE_ROOT
    blocks = (1, 2, 3) if mode == "production" else (1,)
    # Small-budget smoke exercises a regular cut AND final cut with the same
    # K3 protocol. Its fees are SYSTEM consumption, never paired experiment data.
    cuts = [10000000, 20000000, 50000000, 100000000] if mode == "production" else [500000, 1000000]
    trajectories = []
    roles = catalogue()
    for block in blocks:
        t = f"count14-dynteam-70e2ca54/{mode}/b{block}/seed-{SEEDS[block - 1]}"
        trajectories.append(dict(trajectory_id=t, block=block, search_seed=SEEDS[block - 1],
                                 root=f"{root}/b{block}", stable_billing_roles=list(roles),
                                 role_kinds=roles.copy(), request_cap=32,
                                 checkpoints_tokens=cuts.copy(), search_tokens=cuts[-1],
                                 initial_active_roles=["worker-00", "checker-00", "tester-00"],
                                 native_slots={r: f"worker{int(r.split('-')[1]) + 1}" if k == "worker" else
                                               "tester1" if k == "tester" else "checker" for r, k in roles.items()},
                                 lifetime_birth_limit=None,
                                 fees_domain="SEARCH" if mode == "production" else "SYSTEM_SMOKE"))
    return dict(schema="count14-dynteam-public-contract-v1", mode=mode, root=root,
                source_commit=COMMIT, design_sha256=digest(design), source_audit_sha256=digest(source_audit),
                trajectories=trajectories,
                # These baseline reference pins are NOT claims that the NEW
                # bridge/role prompts/images match old v2 source bytes.
                v2_baseline_reference_protocol=deepcopy(source_audit["v2_baseline_reference_protocol"]),
                fixed_model_billing_conditions="ORIGINAL_V2_PARAMETERS_ADAPTER_UNKNOWN_RETRY_NO_REPLAY",
                treatment_orchestration_source=COMMIT,
                native_live_worker_slots=32, initial_workers=1, initial_checker=1, initial_tester=1,
                capacities={"per_trajectory_SEARCH": 32, "own_relay_all_roots_global": 96,
                            "SEARCH_global": 80, "AUX_global": 16, "FINAL_jobs_global": 12,
                            "independent_SYSTEM_probe_slot_reserved_within_physical96": True},
                finalization={"K": 3, "protocol": "v2.1", "official_feedback_to_SEARCH": False,
                              "eval_docker_socket": EVAL_SOCKET,
                              "requires_dynamic_roster_and_retired_archive_snapshot_adapter": True},
                metadata={"schema": "count14-dynteam-anonymous-roster-v1", "no_science_payload": True,
                          "worker_and_all_model_agent_counts_separate": True,
                          "axes": ["UTC", "monotonic_observation_time", "actual_SEARCH_token_budget"],
                          "not_claimed_pause_adjusted_active_runtime": True},
                runtime_ready=False, actual_Dev4_smoke_pass=False,
                mode_is_not_activation_authorization=True)
