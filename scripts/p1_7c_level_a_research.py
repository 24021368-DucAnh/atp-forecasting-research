"""Aggregate-only P1.7c reproduction on immutable TML source snapshots."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile

from atp_gate.tml_elo_experiment import _load, _Ratings, _score, run_tml_elo_experiment
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import PINS, verified_blob

SHA256 = {
    2021: "80d570be31d778b143eb58380258243785bf3fcb18db144b42704bc6c56d941b",
    2022: "d70036c6ee6c27dd3deda6e6c9ccd500b66e6e78106fb00794cb277e37353357",
    2023: "9faaf53186ef908b3322d521a8dd2a717401167c0e400a99e1efddb23e13600f",
    2024: "db27fb184b62bc1716ecc84c5a8365088e34e8e9a0101a59782ec7907f6e2de8",
    2025: "a00f5f991b4949c2c6867637ac02a8c44b9058780da67aba8600e9140002f8d3",
}
NEW_SHA = "5ccf52d912085d6a5ba3effdc5f2f216f170aabfd8850086b5f92c7ccedfd53e"
ADDED_EVENTS = frozenset({"2024-451", "2024-7480"})
YEARS = (2023, 2024, 2025)


def predictions(matches):
    """Replay the locked event timeline for aggregate matched-cohort diagnostics."""
    groups = defaultdict(list)
    for match in matches:
        groups[match.start].append(match)
    days = sorted(groups)
    state = _Ratings()
    matured = 0
    rows = {year: [] for year in YEARS}
    for i, start in enumerate(days):
        while matured < i and days[matured] + timedelta(days=28) <= start:
            state.update_matured_date(groups[days[matured]])
            matured += 1
        if start.year in rows:
            for match in groups[start]:
                g, s = state.probabilities(match)
                rows[start.year].append((match.event_id, match.outcome_a, g, s))
    return [r for year in YEARS for r in rows[year]]


def compare(paths, label, expected_base_count, expected_eligible):
    base = run_tml_elo_experiment(paths, bootstrap_replicates=50)
    normalized = run_tml_elo_experiment(paths, normalize_level_a_2024=True,
                                        bootstrap_replicates=50)
    if (base["test_matches"], base["source_match_rows_eligible"]) != (
            expected_base_count, expected_eligible):
        raise ValueError("locked baseline counts differ")
    for report in (base, normalized):
        if (report["allocation_enabled"] or report["stake"] != 0
                or report["model_validation_trusted"] or report["market_edge_verified"]):
            raise ValueError("research boundary violated")
    if (normalized["test_matches"] != expected_base_count + 53
            or normalized["source_match_rows_eligible"] != expected_eligible + 53
            or normalized["level_a_normalization"]["raw_rows"] != 54
            or normalized["level_a_normalization"]["eligible_rows"] != 53):
        raise ValueError("level-A corrected cohort differs from reviewed source")
    a, _, _, _, _ = _load(paths)
    b, _, _, _, _ = _load(paths, normalize_level_a_2024=True)
    if a != [m for m in b if m.event_id not in ADDED_EVENTS]:
        raise ValueError("original cohort records changed")
    old = predictions(a)
    new = predictions(b)
    same = [r for r in new if r[0] not in ADDED_EVENTS]
    added = [r for r in new if r[0] in ADDED_EVENTS]
    if len(old) != len(same) or len(added) != 53:
        raise ValueError("cohort reconciliation failed")
    for observed, report in ((_score(old), base), (_score(new), normalized)):
        for k, v in report["aggregate"].items():
            if not math.isclose(observed[k], v, rel_tol=0, abs_tol=1e-12):
                raise ValueError("diagnostic replay differs from public experiment")
    return {
        "schema": "TML_LEVEL_A_2024_SENSITIVITY_V1",
        "status": "HISTORICAL_SKILL_RESEARCH_ONLY",
        "source_variant": label,
        "source_inventory": base["source_inventory"],
        "registry": normalized["level_a_normalization"],
        "baseline": {"eligible": base["source_match_rows_eligible"],
                     "folds": base["folds"], "aggregate": base["aggregate"],
                     "excluded": base["excluded_reasons"]},
        "normalized": {"eligible": normalized["source_match_rows_eligible"],
                       "folds": normalized["folds"], "aggregate": normalized["aggregate"],
                       "excluded": normalized["excluded_reasons"]},
        "matched_cohort": {"before": _score(old), "after": _score(same)},
        "added_cohort": _score(added),
        "official_match_draw_verified": False,
        "model_validation_trusted": False, "market_edge_verified": False,
        "allocation_enabled": False, "stake": 0,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="tml-level-a-") as tmp:
        root = Path(tmp)
        paths = []
        for year, pin in sorted(PINS.items()):
            data = verified_blob(pin)
            digest = hashlib.sha256(data).hexdigest()
            if digest != SHA256[year]:
                raise ValueError("original source SHA256 mismatch")
            path = root / f"{year}-{digest}.csv"
            path.write_bytes(data)
            paths.append(path)
        print(json.dumps(compare(paths, "ORIGINAL_PINNED", 7194, 12123),
                         sort_keys=True), flush=True)
        receipt = update_tml_season(2025, root, at=datetime.now(timezone.utc))
        revised = Path(receipt["local_snapshot"])
        if hashlib.sha256(revised.read_bytes()).hexdigest() != NEW_SHA:
            raise ValueError("revised source SHA256 drift; do not substitute a different version")
        print(json.dumps(compare(paths[:4] + [revised], "REVISED_2025_PINNED",
                                 7641, 12570), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
