"""One-off aggregate-only source revision sensitivity, not model selection."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from atp_gate.tml_elo_experiment import run_tml_elo_experiment
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import PINS, verified_blob
from scripts.tml_2025_revision_audit import _parse

NEW_SHA = "5ccf52d912085d6a5ba3effdc5f2f216f170aabfd8850086b5f92c7ccedfd53e"

def event_summary(rows, event):
    selected = [r for r in rows if r["tourney_id"] == event]
    return {"n":len(selected), "dates":dict(Counter(r["tourney_date"] for r in selected)),
            "surfaces":dict(Counter(r["surface"] for r in selected)),
            "levels":dict(Counter(r["tourney_level"] for r in selected))}

def main():
    with tempfile.TemporaryDirectory(prefix="tml-source-sensitivity-") as tmp:
        root=Path(tmp)
        common=[]
        for year in (2021,2022,2023,2024):
            data=verified_blob(PINS[year])
            path=root/f"{year}-{hashlib.sha256(data).hexdigest()}.csv"
            path.write_bytes(data)
            common.append(path)
        old=verified_blob(PINS[2025])
        old_path=root/f"2025-{hashlib.sha256(old).hexdigest()}.csv"
        old_path.write_bytes(old)
        receipt=update_tml_season(2025,root,at=datetime.now(timezone.utc))
        new_path=Path(receipt["local_snapshot"])
        new=new_path.read_bytes()
        if hashlib.sha256(new).hexdigest()!=NEW_SHA:
            raise ValueError("publisher source hash changed")
        old_rows,_=_parse(old)
        new_rows,_=_parse(new)
        events={event:{"old":event_summary(old_rows,event),"new":event_summary(new_rows,event)}
                for event in ("2025-5014","2025-8996")}
        a=run_tml_elo_experiment(common+[old_path])
        b=run_tml_elo_experiment(common+[new_path])
        if a["test_matches"]!=7194 or a["source_match_rows_eligible"]!=12123:
            raise ValueError("original locked baseline not reproduced")
        for report in (a,b):
            if report["allocation_enabled"] or report["stake"]!=0 or report["model_validation_trusted"]:
                raise ValueError("research boundary violated")
        levels=Counter((r["tourney_id"],r["tourney_name"]) for r in new_rows if r["tourney_level"]=="A")
        print(json.dumps({
            "status":"DESCRIPTIVE_SOURCE_SENSITIVITY_ONLY",
            "source_sha256":NEW_SHA, "publisher_url":receipt["source_url"],
            "retrieved_at":receipt["checked_at_utc"],
            "event_metadata":events,
            "level_a_event_inventory_2025":[{"event":e,"name":n,"rows":v} for (e,n),v in sorted(levels.items())],
            "old":{"n":a["test_matches"],"eligible":a["source_match_rows_eligible"],"folds":a["folds"],"aggregate":a["aggregate"],"excluded":a["excluded_reasons"]},
            "revised":{"n":b["test_matches"],"eligible":b["source_match_rows_eligible"],"folds":b["folds"],"aggregate":b["aggregate"],"excluded":b["excluded_reasons"]},
            "same_evaluation_cohort":False, "official_match_draw_verified":False,
            "model_validation_trusted":False,"market_edge_verified":False,
            "allocation_enabled":False,"stake":0
        },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
