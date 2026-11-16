"""Pure pre-run two-arm contract. NOT an owner/activation entry."""
from copy import deepcopy
from dynteam_metadata import COMMIT, catalogue, digest, need
from dynteam_manifest import SEEDS, ROOT, SMOKE_ROOT, EVAL_SOCKET

RACING_SOURCE = "21a0413e3262cebd5c6ac314974710937b9741b0"
RACING_ROOT = "/mnt/ptb-scratch2/count14-dynteam-racing-70e2ca54-21a0413e-20261105"
RACING_SMOKE = "/mnt/ptb-scratch2/count14-dynteam-racing-70e2ca54-21a0413e-smoke-20261105"


def compile_two_arm_contract(design, base_audit, racing_merge, *, mode):
    need(mode in ("production", "smoke"), "DYNTEAM_TWO_ARM_EXPLICIT_MODE")
    need(design["schema"] in ("count14-dynteam-two-arm-preregistered-adaptation-design-v3",
                              "count14-dynteam-two-arm-preregistered-adaptation-design-v4") and
         design["source_commit"] == base_audit["source_commit"] == COMMIT and
         not base_audit["working_copy_missing_orchestration_paths"], "DYNTEAM_TWO_ARM_PINNED_BASE")
    need(racing_merge["base_commit"] == COMMIT and racing_merge["racing_source_commit"] == RACING_SOURCE and
         type(racing_merge["merged_commit"]) is str and len(racing_merge["merged_commit"]) == 40 and
         all(c in "0123456789abcdef" for c in racing_merge["merged_commit"]) and
         racing_merge["base_original_science_tree_unchanged_outside_listed_paths"] is True and
         racing_merge["upstream_worktree_HEAD_unchanged"] is True, "DYNTEAM_TWO_ARM_REAL_SELECTIVE_MERGE")
    need(tuple((r["block"], r["search_seed"], r["paired_v2_seed"]) for r in design["trajectories"]) ==
         tuple((b, s, s) for b, s in enumerate(SEEDS, 1)), "DYNTEAM_TWO_ARM_PAIRED_B1_B3")
    need(design["search_budget_tokens_per_trajectory"] == 100000000 and
         design["checkpoints_tokens"] == [10000000, 20000000, 50000000, 100000000] and
         design["finalization"] == {"K": 3, "official_test_feedback_to_SEARCH": False,
                                    "protocol": "v2.1", "separate_AUX_accounting": True},
         "DYNTEAM_TWO_ARM_SAME_100M_K3")
    limits = design["external_FP8_limits"]
    need(all(limits[k] == v for k, v in {
        "per_trajectory_inflight_upper": 13, "SEARCH_six_trajectories_global_upper": 78,
        "AUX_global_upper": 16, "FINAL_global_upper": 12, "SYSTEM_probe_reserved_slots": 2,
        "all_own_relay_roots_inflight_upper": 96, "physical_max_sum": 96}.items()) and
        limits["global_gateway_load_not_admission_counter"] is True,
        "DYNTEAM_TWO_ARM_SAME_CAP13_PHYSICAL96")
    expected = [("DYNTEAM", ROOT, SMOKE_ROOT), ("DYNTEAM_RACING", RACING_ROOT, RACING_SMOKE)]
    need([(a["arm"], a["root"], a["smoke_root"]) for a in design["arms"]] == expected,
         "DYNTEAM_TWO_ARM_EXACT_NEW_ROOTS")
    trajectories, arms = [], []
    for arm, formal_root, smoke_root in expected:
        root = formal_root if mode == "production" else smoke_root
        racing = arm == "DYNTEAM_RACING"
        roles = catalogue(racing_players=7 if racing else 0)
        selected = (1, 2, 3) if mode == "production" else (1,)
        cuts = design["checkpoints_tokens"] if mode == "production" else [500000, 1000000]
        arm_rows = []
        for block in selected:
            t = f"count14-dynteam{'-racing' if racing else ''}/{mode}/b{block}/seed-{SEEDS[block - 1]}"
            row = dict(arm=arm, trajectory_id=t, root=f"{root}/b{block}", block=block,
                       search_seed=SEEDS[block - 1], paired_v2_seed=SEEDS[block - 1],
                       roles=list(roles), role_kinds=roles, request_cap=13, search_tokens=cuts[-1],
                       checkpoints_tokens=list(cuts), lifetime_agent_birth_limit=None,
                       initial_active_roles=["worker-00", "checker-00", "tester-00"],
                       base_native_commit=COMMIT, orchestration_commit=racing_merge["merged_commit"] if racing else COMMIT,
                       every_model_role_charged=True, fees_domain="SEARCH" if mode == "production" else "SYSTEM_SMOKE")
            trajectories.append(row)
            arm_rows.append(t)
        arms.append(dict(arm=arm, root=root, trajectories=arm_rows, native_catalogue=roles,
                         source_commit=racing_merge["merged_commit"] if racing else COMMIT))
    execution = design.get("racing_execution")
    if design["schema"].endswith("-v4"):
        need(execution == {
            "method": "m7", "judge": "COUNT14_ORIGINAL_SEARCH_PUBLIC_TASK_TOOLS",
            "reproducibility_runs": 2, "private_reference_or_official_feedback": False,
            "retain_run_feedback_defend_revision_and_signature_novelty": True},
            "DYNTEAM_RACING_FORMAL_FULL_EXECUTING_M7_NOT_THINKING_ONLY")
    result = dict(schema="count14-dynteam-two-arm-public-contract-v1", mode=mode,
                trajectories=trajectories, arms=arms,
                design_sha256=digest(design), source_inventory_sha256=digest(base_audit),
                racing_merge_manifest_sha256=digest(racing_merge),
                v2_baseline_reference_protocol=deepcopy(base_audit["v2_baseline_reference_protocol"]),
                v2_reference_is_not_new_runtime_qualification=True,
                capacities={"per_track_SEARCH": 13, "SEARCH_total": 78, "AUX_total": 16,
                            "FINAL_jobs": 12, "SYSTEM_probe_reserved": 2, "all_own_relay_physical": 96},
                admission_uses_original_relay_counts_across_all_own_roots=True,
                affinity_domain="ONE_SHARED_DOMAIN_ALL_SIX_TRACKS_ALL_ROLE_BIRTHS",
                racing={"source_commit": RACING_SOURCE, "merged_commit": racing_merge["merged_commit"],
                        "players": 7, "background_roles": 1, "method": "m4", "judge": "none",
                        "trigger": "600_PAUSE_AWARE_ACTIVE_SECONDS_NO_ORIGINAL_PUBLIC_PROGRESS",
                        "round_active_seconds": 600, "semantic_quorum": 0.75,
                        "physical_tail": "RETAIN_NATURAL_TERMINAL_CHARGE_ALL_NO_CANCEL_NO_REPLAY",
                        "proposals": "UNVERIFIED_PUBLIC_TEST_DEVELOPMENT_NOT_OFFICIAL_VERDICTS",
                        "native_USD_ledger_and_HTTP_retries_enabled": False},
                finalization={"K": 3, "protocol": "v2.1", "eval_docker_socket": EVAL_SOCKET,
                              "official_feedback_to_SEARCH": False, "separate_AUX": True},
                runtime_ready=False, actual_Dev4_smoke_pass=False,
                production_activation_authorized_by_this_contract=False)
    if execution is not None:
        result["racing"].update(method="m7", judge="COUNT14_ORIGINAL_SEARCH_PUBLIC_TASK_TOOLS",
            reproducibility_runs=2, private_reference_or_official_feedback=False,
            run_feedback_defend_revision_and_signature_novelty=True,
            proposals="PUBLIC_TOOL_VALIDATED_REPRODUCTIONS_NOT_OFFICIAL_VERDICTS")
    else:
        result["racing"]["legacy_OWN_or_audit_configuration_not_formal_scientific_treatment"] = True
    return result
