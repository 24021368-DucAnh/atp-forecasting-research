"""Verify the locked research candidate; emit aggregate evidence and review leads."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile

from atp_gate.tml_cohort_manifest import cohort_manifest, profile_identity_variants, verify_pinned_inputs
from atp_gate.tml_duplicate_sensitivity import derive_duplicate_snapshot
from atp_gate.tml_elo_experiment import _load, run_tml_elo_experiment
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import PINS, verified_blob
from scripts.p1_7c_level_a_research import SHA256


def main():
    m = cohort_manifest()
    with tempfile.TemporaryDirectory(prefix="tml-cohort-") as folder:
        root = Path(folder)
        old = {y: verified_blob(pin) for y, pin in sorted(PINS.items())}
        verify_pinned_inputs(old, SHA256)
        receipt = update_tml_season(2025, root, at=datetime.now(timezone.utc))
        current = {**old, 2025: Path(receipt["local_snapshot"]).read_bytes()}
        # Verify every original source before profiling, transforming or replay.
        verify_pinned_inputs(current, m["original_sha256"])
        derived, receipts = {}, []
        for y, raw in sorted(current.items()):
            derived[y], rec = derive_duplicate_snapshot(
                raw, season=y, expected_sha256=m["original_sha256"][y],
                expected_exact_groups=m["exact_groups_by_season"][y],
                expected_conflicting_groups=m["conflicting_groups_by_season"][y],
                mode=m["duplicate_mode"])
            receipts.append(rec)
        verify_pinned_inputs(derived, m["derived_sha256"])
        if sum(r["removed_rows"] for r in receipts) != 3:
            raise ValueError("unexpected derived cohort removal count")
        folder = root / "derived"
        folder.mkdir()
        paths = []
        for y, data in sorted(derived.items()):
            path = folder / f"{y}-{m['derived_sha256'][y]}.csv"
            path.write_bytes(data)
            paths.append(path)
        report = run_tml_elo_experiment(paths, normalize_level_a_2024=True,
                                        embargo_days=m["embargo_days"], bootstrap_replicates=50)
        actual_folds = {f["year"]: f["n"] for f in report["folds"]}
        if (report["source_match_rows_eligible"] != m["expected_eligible"]
                or report["test_matches"] != m["expected_evaluated"]
                or actual_folds != m["evaluation_by_year"]
                or report["level_a_normalization"]["registry_sha256"] != m["level_a_registry_sha256"]
                or report["elo_k_fixed"] != m["elo_k"]
                or report["surface_weight_fixed"] != m["surface_weight"]):
            raise ValueError("locked cohort count or configuration drift")
        for key in ("global", "surface"):
            if not math.isclose(report["aggregate"][key+"_elo_log_loss"],
                                m["expected_"+key+"_log_loss"], abs_tol=1e-12, rel_tol=0):
                raise ValueError("locked Elo reference drift")
        if report["model_validation_trusted"] or report["allocation_enabled"] or report["stake"] != 0:
            raise ValueError("research boundary violated")
        matches, _, _, _, _ = _load(paths, normalize_level_a_2024=True)
        old_profile = profile_identity_variants(old.values())
        revised_profile = profile_identity_variants(current.values())
        final_profile = profile_identity_variants(derived.values())
        if (old_profile["multiple_name_ids"], revised_profile["multiple_name_ids"],
                final_profile["multiple_name_ids"]) != (1,2,2):
            raise ValueError("identity-review group drift")
        if any(p["multiple_id_names"] for p in (old_profile, revised_profile, final_profile)):
            raise ValueError("unexpected name-to-multiple-ID conflict")
        # Private research job: only two aggregate name/ID review leads, no match rows.
        leads = []
        for item in final_profile["variants"]:
            pid = item["player_id"]
            affected = [x for x in matches if pid in (x.player_a, x.player_b)]
            leads.append({**item, "eligible_rows": len(affected),
                          "evaluated_rows": sum(x.start.year in m["evaluation_by_year"] for x in affected)})
        print(json.dumps({"kind":"IDENTITY_REVIEW_LEADS_LOCAL_ONLY", "leads":leads}, sort_keys=True), flush=True)
        output = {
            "schema": "TML_COHORT_MANIFEST_REPLAY_V1",
            "manifest": m,
            "manifest_sha256": hashlib.sha256(json.dumps(m, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "source_receipts": receipts,
            "eligible": len(matches),
            "evaluation_folds": actual_folds,
            "aggregate": report["aggregate"],
            "identity_summary": {
                "old_multiple_name_ids": old_profile["multiple_name_ids"],
                "revised_multiple_name_ids": revised_profile["multiple_name_ids"],
                "derived_multiple_name_ids": final_profile["multiple_name_ids"],
                "derived_multiple_id_names": final_profile["multiple_id_names"],
                "variant_ids_with_eligible_rows": sum(x["eligible_rows"] > 0 for x in leads),
                "identity_remapped": False,
            },
            "official_match_draw_verified": False,
            "model_validation_trusted": False,
            "allocation_enabled": False,
            "stake": 0,
        }
        print(json.dumps(output, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
