"""Immutable synthetic evaluation receipts and fixed prospective cohorts."""
from collections import Counter
from dataclasses import asdict, dataclass, replace
import json
import sqlite3

from atp_lab.database import forecast
from atp_lab.database.identity import utc_timestamp
from atp_lab.database.schema_v4 import evaluation_transaction
from atp_lab.prediction.commitment import (
    SCOPE, UnverifiedCommitment, _get_commitment, _hash, _id, _json,
    _require_new_target, _stable_id,
)
from .eligibility import Assessment, decide, fixture_eligible, fixture_info
from .metrics import matched_metrics, score_metrics

COHORT_VERSION = "S5_SYNTHETIC_COHORT_1"
MAX_COHORT_PAIRS = 100000
_STATUSES = ("INELIGIBLE", "MISSING", "PENDING", "RECORDED", "VOID")


@dataclass(frozen=True)
class Cohort:
    cohort_id: str
    registered_at: str
    cutoff_end: str
    fixture_ids: tuple[str, ...]
    model_ids: tuple[str, ...]
    digest: str


def _ids(values):
    if type(values) not in (tuple, list) or not values or len(values) > MAX_COHORT_PAIRS:
        raise ValueError("invalid cohort identity inventory")
    result = tuple(sorted(_id(x) for x in values))
    if len(set(result)) != len(result):
        raise ValueError("duplicate cohort identity")
    return result


def _read_cohort(conn, cohort_id):
    row = conn.execute(
        "SELECT registered_at,cutoff_end,payload,digest FROM evaluation_cohorts WHERE cohort_id=?",
        (cohort_id,)).fetchone()
    if row is None:
        return None
    registered, end, raw, digest = row
    try:
        payload = json.loads(raw)
        members = payload["fixtures"]
        fixtures = _ids([x["fixture_id"] for x in members])
        models = _ids(payload["model_ids"])
        if (type(payload) is not dict or _json(payload) != raw or _hash(raw) != digest
                or payload["version"] != COHORT_VERSION or payload["scope"] != SCOPE
                or payload["cohort_id"] != cohort_id or payload["registered_at"] != registered
                or payload["cutoff_end"] != end or utc_timestamp(registered) != registered
                or utc_timestamp(end) != end or registered > end
                or tuple(x["fixture_id"] for x in members) != fixtures
                or tuple(payload["model_ids"]) != models
                or len(fixtures) * len(models) > MAX_COHORT_PAIRS
                or len({x["match_id"] for x in members}) != len(members)):
            raise ValueError("cohort receipt mismatch")
        for member in members:
            info = fixture_info(conn, member["fixture_id"])
            if member != _member(info):
                raise ValueError("cohort member lineage mismatch")
    except (KeyError, TypeError, IndexError, ValueError):
        raise ValueError("invalid cohort receipt") from None
    return Cohort(cohort_id, registered, end, fixtures, models, digest), members


def _member(info):
    return {key: info[key] for key in
            ("fixture_id", "match_id", "source_id", "scheduled_start", "tier", "surface")}


def register_cohort(conn: sqlite3.Connection, cohort_id: str, fixture_ids, model_ids,
                    *, registered_at: str, cutoff_end: str) -> Cohort:
    """Freeze the full denominator before any member outcome is stored."""
    _id(cohort_id)
    registered, end = utc_timestamp(registered_at), utc_timestamp(cutoff_end)
    fixtures, models = _ids(fixture_ids), _ids(model_ids)
    if registered > end or len(fixtures) * len(models) > MAX_COHORT_PAIRS:
        raise ValueError("invalid cohort window or size")
    with evaluation_transaction(conn, write=True):
        existing = _read_cohort(conn, cohort_id)
        if existing is not None:
            old, _ = existing
            if (old.registered_at, old.cutoff_end, old.fixture_ids, old.model_ids) != (registered, end, fixtures, models):
                raise ValueError("conflicting immutable cohort replay")
            return old
        for model_id in models:
            model = conn.execute(
                "SELECT training_cutoff,created_at,scope FROM model_versions WHERE model_id=?",
                (model_id,)).fetchone()
            if (model is None or model[2] != "SYNTHETIC"
                    or not utc_timestamp(model[0]) <= utc_timestamp(model[1]) <= registered):
                raise ValueError("cohort model unavailable at registration")
        members = []
        seen_matches = set()
        for fixture_id in fixtures:
            info = fixture_info(conn, fixture_id)
            if not fixture_eligible(info, registered) or info["match_id"] in seen_matches:
                raise ValueError("ineligible or duplicate cohort match")
            _require_new_target(conn, fixture_id, info["match_id"])
            seen_matches.add(info["match_id"])
            members.append(_member(info))
        raw = _json({"version": COHORT_VERSION, "scope": SCOPE, "cohort_id": cohort_id,
                     "registered_at": registered, "cutoff_end": end,
                     "fixtures": members, "model_ids": models})
        digest = _hash(raw)
        conn.execute("INSERT INTO evaluation_cohorts VALUES (?,?,?,?,?)",
                     (cohort_id, registered, end, raw, digest))
        return Cohort(cohort_id, registered, end, fixtures, models, digest)


def _stored_assessment(conn, prediction_id, decision, as_of):
    if decision.result_id is None or decision.status == "PENDING":
        return decision
    row = conn.execute(
        "SELECT e.evaluation_id,e.evaluated_at,e.status,a.reason,a.outcome_a "
        "FROM evaluations e LEFT JOIN assessment_receipts a ON a.evaluation_id=e.evaluation_id "
        "WHERE e.prediction_id=? AND e.result_id=?",
        (prediction_id, decision.result_id)).fetchone()
    if row is None:
        return None
    if row[1] > as_of:
        return Assessment("PENDING", "NOT_EVALUATED", decision.result_id)
    if tuple(row[2:]) != (decision.status, decision.reason, decision.outcome_a):
        raise ValueError("conflicting immutable assessment evidence")
    return replace(decision, evaluation_id=row[0], evaluated_at=row[1])


def evaluate_prediction(conn: sqlite3.Connection, prediction_id: str, *, as_of: str) -> Assessment:
    """Append the terminal assessment for the effective available revision."""
    limit = utc_timestamp(as_of)
    with evaluation_transaction(conn, write=True):
        commitment = _get_commitment(conn, prediction_id)
        decision = decide(conn, commitment, limit)
        existing = _stored_assessment(conn, prediction_id, decision, limit)
        if existing is not None:
            return existing
        eid = _stable_id("evaluation", COHORT_VERSION, prediction_id, decision.result_id)
        forecast.append_evaluation(conn, forecast.Evaluation(
            eid, prediction_id, decision.result_id, limit, decision.status))
        conn.execute("INSERT INTO assessment_receipts VALUES (?,?,?)",
                     (eid, decision.reason, decision.outcome_a))
        return replace(decision, evaluation_id=eid, evaluated_at=limit)


def _report_row(conn, member, model_id, cohort, limit):
    pred = conn.execute(
        "SELECT prediction_id,created_at FROM predictions WHERE fixture_id=? AND model_id=? "
        "AND created_at<=?", (member["fixture_id"], model_id, limit)).fetchone()
    if pred is None:
        return member, False, "MISSING", "NO_PREDICTION", None
    try:
        committed = _get_commitment(conn, pred[0])
    except UnverifiedCommitment:
        return member, False, "MISSING", "UNVERIFIED_COMMITMENT", None
    if not cohort.registered_at <= committed.prediction.created_at <= cohort.cutoff_end:
        return member, False, "MISSING", "OUTSIDE_COHORT_WINDOW", None
    decision = decide(conn, committed, limit)
    assessment = _stored_assessment(conn, pred[0], decision, limit)
    if assessment is None:
        assessment = Assessment("PENDING", "NOT_EVALUATED", decision.result_id)
    sample = None
    if assessment.status == "RECORDED":
        sample = (committed.prediction.probability_a, assessment.outcome_a, assessment.result_id)
    return member, True, assessment.status, assessment.reason, sample


def _summarize(rows):
    n = len(rows)
    status = dict.fromkeys(_STATUSES, 0)
    reasons = Counter()
    samples = []
    committed = 0
    for _, has_commitment, state, reason, sample in rows:
        committed += int(has_commitment)
        status[state] += 1
        reasons[reason] += 1
        if sample is not None:
            samples.append(sample[:2])
    scored = len(samples)
    return {
        "target_n": n, "committed_n": committed, "scored_n": scored,
        "prediction_coverage": committed / n if n else None,
        "scored_coverage": scored / n if n else None,
        "status_counts": status, "reason_counts": dict(sorted(reasons.items())),
        "metrics": asdict(score_metrics(samples)),
    }


def _groups(rows):
    dimensions = {"tier": lambda m: m["tier"], "surface": lambda m: m["surface"],
                  "month": lambda m: m["scheduled_start"][:7]}
    grouped = {}
    for name, key in dimensions.items():
        by = {}
        for row in rows:
            by.setdefault(key(row[0]), []).append(row)
        grouped[name] = {value: _summarize(by[value]) for value in sorted(by)}
    return grouped


def evaluation_report(conn: sqlite3.Connection, cohort_id: str, *, as_of: str):
    """Read-only as-of cohort; corrections never increase the denominator."""
    _id(cohort_id)
    limit = utc_timestamp(as_of)
    with evaluation_transaction(conn, write=False):
        receipt = _read_cohort(conn, cohort_id)
        if receipt is None:
            raise ValueError("unknown evaluation cohort")
        cohort, members = receipt
        if limit < cohort.registered_at:
            raise ValueError("report precedes cohort registration")
        summaries, matched = {}, {}
        for model_id in cohort.model_ids:
            rows = [_report_row(conn, member, model_id, cohort, limit) for member in members]
            summaries[model_id] = {**_summarize(rows), "groups": _groups(rows)}
            matched[model_id] = {row[0]["fixture_id"]: row[4] for row in rows if row[4] is not None}
        return {"cohort_id": cohort.cohort_id, "cohort_digest": cohort.digest,
                "scope": SCOPE, "as_of": limit, "registered_at": cohort.registered_at,
                "cutoff_end": cohort.cutoff_end, "models": summaries,
                "matched": matched_metrics(matched)}
