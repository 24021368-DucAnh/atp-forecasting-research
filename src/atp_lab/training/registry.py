"""Controlled candidate fit, immutable registry, comparison and manual lifecycle.

The public training entrypoint accepts a registered protocol ID, never a
caller-supplied feature matrix or estimator. Every operation is synthetic.
"""
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sqlite3

from atp_lab.database import forecast
from atp_lab.database.identity import utc_timestamp
from atp_lab.database.schema_v5 import training_transaction
from atp_lab.evaluation import service
from atp_lab.evaluation.eligibility import fixture_info
from atp_lab.evaluation.metrics import matched_metrics
from atp_lab.prediction import commitment, inference
from atp_lab.prediction.features import FEATURE_NAMES, FEATURE_VERSION
from .artifact import (ARTIFACT_VERSION, artifact_directory, decode_artifact,
                       publish_artifact, read_artifact)
from .dataset import (_collect, _mature_match_ids, _previously_recorded_mature_matches,
                      dataset_payload, validate_dataset)
from .fit import fit_logistic
from .protocol import _read_protocol, fixed_config, protocol_payload, require_digest

LIFECYCLE_VERSION = "S6_SYNTHETIC_LIFECYCLE_1"
COMPARISON_VERSION = "S6_SYNTHETIC_MATCHED_COMPARISON_1"
MAX_EVENTS = 4096


def _digest(value):
    return commitment._hash(commitment._json(value))


def _provenance():
    deps = {"python": platform.python_version(), "platform": platform.system()}
    for package in ("numpy", "scikit-learn", "scipy", "threadpoolctl", "joblib"):
        deps[package] = version(package)
    root = Path(__file__).resolve().parents[1]
    paths = (
        "training/protocol.py", "training/dataset.py", "training/artifact.py",
        "training/fit.py", "training/registry.py", "database/schema_v5.py",
        "prediction/features.py", "prediction/temporal.py", "prediction/inference.py",
        "prediction/commitment.py", "evaluation/eligibility.py", "evaluation/service.py",
        "evaluation/metrics.py",
    )
    code = {p: sha256((root / p).read_bytes()).hexdigest() for p in paths}
    return deps, code


def _model_version(receipt):
    return forecast.ModelVersion(receipt.model_id, receipt.model_digest,
        receipt.config_digest, receipt.training_cutoff, receipt.created_at, "SYNTHETIC")


def _require_v5(conn):
    if conn.execute("PRAGMA user_version").fetchone()[0] != 5:
        raise ValueError("verified synthetic training schema v5 required")


def _stored_candidate(conn, model_id):
    """Inside a verified snapshot: validate frozen DB bytes and model linkage."""
    _require_v5(conn)
    commitment._id(model_id)
    row = conn.execute(
        "SELECT c.protocol_id,c.payload,m.model_id,m.model_digest,m.config_digest,"
        "m.training_cutoff,m.created_at,m.scope FROM candidate_artifacts c "
        "JOIN model_versions m ON m.model_id=c.model_id WHERE c.model_id=?",
        (model_id,)).fetchone()
    if row is None:
        raise ValueError("unregistered synthetic candidate")
    protocol_id, raw, *model = row
    candidate = decode_artifact(raw)
    if (candidate.receipt.model_id != model_id
            or candidate.receipt.protocol_id != protocol_id
            or _read_protocol(conn, protocol_id) != candidate.protocol
            or _model_version(candidate.receipt) != forecast.ModelVersion(*model)):
        raise ValueError("candidate registry lineage mismatch")
    return candidate, raw


def _load_candidate(conn, model_id, model_dir):
    candidate, raw = _stored_candidate(conn, model_id)
    local, _ = read_artifact(model_dir, model_id)
    if local != raw:
        raise ValueError("artifact differs from immutable registry")
    return candidate


def load_verified_candidate(conn: sqlite3.Connection, model_id: str, *, model_dir):
    with training_transaction(conn, write=False):
        return _load_candidate(conn, model_id, model_dir)


def _existing(conn, protocol, created, model_dir):
    row = conn.execute("SELECT model_id FROM candidate_artifacts WHERE protocol_id=?",
                       (protocol.protocol_id,)).fetchone()
    if row is None:
        return None
    candidate = _load_candidate(conn, row[0], model_dir)
    if candidate.receipt.created_at != created or candidate.protocol != protocol:
        raise ValueError("conflicting frozen candidate replay")
    return candidate.receipt


def _ensure_future_cohort_unregistered(conn, protocol):
    if conn.execute("SELECT 1 FROM evaluation_cohorts WHERE cohort_id=?",
                    (protocol.evaluation_cohort_id,)).fetchone():
        raise ValueError("candidate must freeze before future cohort registration")


def train_candidate(conn: sqlite3.Connection, protocol_id: str, *,
                    created_at: str, model_dir):
    """Manual synthetic fit; fit outside writer lock, revalidate before publication.

    A failure after publication but before DB commit can leave a harmless,
    hash-named orphan. No file is deleted or overwritten automatically.
    """
    created = utc_timestamp(created_at)
    root = artifact_directory(model_dir)
    with training_transaction(conn, write=False):
        p = _read_protocol(conn, protocol_id)
        if not p.training_cutoff < created <= p.evaluation_start:
            raise ValueError("candidate freeze clock outside registered window")
        existing = _existing(conn, p, created, root)
        if existing is not None:
            return existing
        _ensure_future_cohort_unregistered(conn, p)
        data = validate_dataset(_collect(conn, p), p, support=True)

    params = fit_logistic(data)
    deps, code = _provenance()
    config = fixed_config()
    raw = commitment._json({
        "version": ARTIFACT_VERSION, "scope": "SYNTHETIC",
        "feature_version": FEATURE_VERSION, "feature_names": list(FEATURE_NAMES),
        "protocol": protocol_payload(p), "protocol_digest": p.digest,
        "dataset": dataset_payload(data), "dataset_digest": data.digest,
        "config": config, "config_digest": _digest(config),
        "dependencies": deps, "dependency_digest": _digest(deps),
        "code": code, "code_digest": _digest(code),
        "training_cutoff": p.training_cutoff, "created_at": created,
        "parameters": asdict(params),
    })
    candidate = decode_artifact(raw)
    with training_transaction(conn, write=True):
        if _read_protocol(conn, protocol_id) != p:
            raise ValueError("protocol changed during fit")
        existing = _existing(conn, p, created, root)
        if existing is not None:
            if existing != candidate.receipt:
                raise ValueError("concurrent conflicting candidate freeze")
            return existing
        _ensure_future_cohort_unregistered(conn, p)
        if _collect(conn, p) != data:
            raise ValueError("training selection changed during fit")
        publish_artifact(root, raw)
        if not forecast.append_model(conn, _model_version(candidate.receipt)):
            raise ValueError("model version exists without matching registry")
        conn.execute("INSERT INTO candidate_artifacts VALUES (?,?,?)",
                     (candidate.receipt.model_id, protocol_id, raw))
    return candidate.receipt


def _candidate_for_inference(conn, model_id, model_dir, cutoff, target):
    candidate = _load_candidate(conn, model_id, model_dir)
    receipt = candidate.receipt
    consumed = (*candidate.dataset.fit, *candidate.dataset.calibration)
    if (receipt.created_at > cutoff or target.event_start <= date.fromisoformat(receipt.training_cutoff[:10])
            or any(target.match_id == row.match_id or target.tournament_id == row.event_id
                   for row in consumed)):
        raise ValueError("candidate unavailable at cutoff or target consumed by training")
    return _model_version(receipt), candidate


def _baseline_version(conn):
    row = conn.execute("SELECT model_id,model_digest,config_digest,training_cutoff,"
                       "created_at,scope FROM model_versions WHERE model_id=?",
                       (inference.MODEL_ID,)).fetchone()
    if row is None:
        raise ValueError("fixed baseline not registered")
    model = forecast.ModelVersion(*row)
    if model != inference.synthetic_model_version(created_at=model.created_at):
        raise ValueError("invalid fixed baseline version")
    return model


def _version_for(conn, model_id):
    if model_id == inference.MODEL_ID:
        return _baseline_version(conn)
    return _model_version(_stored_candidate(conn, model_id)[0].receipt)


def _cohort_for(conn, candidate):
    p, r = candidate.protocol, candidate.receipt
    record = service._read_cohort(conn, p.evaluation_cohort_id)
    if record is None:
        raise ValueError("registered subsequent cohort not found")
    cohort, members = record
    if (cohort.model_ids != tuple(sorted((inference.MODEL_ID, r.model_id)))
            or not r.created_at <= p.evaluation_start <= cohort.registered_at <= p.evaluation_end
            or cohort.cutoff_end != p.evaluation_end):
        raise ValueError("cohort differs from frozen candidate protocol")
    consumed = (*candidate.dataset.fit, *candidate.dataset.calibration)
    consumed_matches = {row.match_id for row in consumed}
    consumed_events = {row.event_id for row in consumed}
    for member in members:
        info = fixture_info(conn, member["fixture_id"])
        if (info["match_id"] in consumed_matches or info["tournament_id"] in consumed_events
                or member["scheduled_start"] <= r.created_at):
            raise ValueError("subsequent cohort overlaps training evidence")
    return cohort, members


def _scored_evidence(conn, fixture_id, model_id, sample, limit):
    """Bind the exact immutable receipts used by a scored report row."""
    probability, outcome, result_id = sample
    row = conn.execute(
        "SELECT p.prediction_id,p.commitment_digest,p.feature_id,f.feature_digest,"
        "p.created_at,e.evaluation_id,e.evaluated_at,p.probability_a,a.outcome_a "
        "FROM predictions p JOIN feature_snapshots f ON f.feature_id=p.feature_id "
        "JOIN evaluations e ON e.prediction_id=p.prediction_id "
        "JOIN assessment_receipts a ON a.evaluation_id=e.evaluation_id "
        "WHERE p.fixture_id=? AND p.model_id=? AND e.result_id=? "
        "AND e.status='RECORDED' AND a.reason='ELIGIBLE' AND e.evaluated_at<=?",
        (fixture_id, model_id, result_id, limit)).fetchone()
    if row is None or tuple(row[-2:]) != (probability, outcome):
        raise ValueError("scored row missing exact assessment evidence")
    keys = ("prediction_id", "commitment_digest", "feature_id", "feature_digest",
            "cutoff", "evaluation_id", "evaluated_at", "probability_a", "outcome_a")
    return {**dict(zip(keys, row)), "result_id": result_id}


def _information_set(evidence):
    return evidence["cutoff"], evidence["feature_digest"]


def _comparison(conn, candidate, limit):
    cohort, members = _cohort_for(conn, candidate)
    r, p = candidate.receipt, candidate.protocol
    if limit < cohort.registered_at:
        raise ValueError("comparison precedes cohort registration")
    base = inference.MODEL_ID
    models = {}
    rows = {}
    for model_id in (base, r.model_id):
        group = [service._report_row(conn, member, model_id, cohort, limit)
                 for member in members]
        rows[model_id] = group
        models[model_id] = {**service._summarize(group), "groups": service._groups(group)}
    samples = {base: {}, r.model_id: {}}
    reasons = Counter()
    matched_evidence, unmatched_evidence = [], []
    for b, a in zip(rows[base], rows[r.model_id]):
        fid = b[0]["fixture_id"]
        evidence = {model_id: None if item[4] is None else
                    _scored_evidence(conn, fid, model_id, item[4], limit)
                    for model_id, item in ((base, b), (r.model_id, a))}
        if b[4] is None or a[4] is None:
            reason = "MISSING_OR_UNSCORED"
        elif b[4][1:] != a[4][1:]:
            reason = "RESULT_REVISION_MISMATCH"
        elif _information_set(evidence[base]) != _information_set(evidence[r.model_id]):
            reason = "DIFFERENT_INFORMATION_SET"
        else:
            samples[base][fid], samples[r.model_id][fid] = b[4], a[4]
            matched_evidence.append({"fixture_id": fid, "result_id": b[4][2],
                                     "outcome_a": b[4][1], "models": evidence})
            continue
        reasons[reason] += 1
        unmatched_evidence.append({"fixture_id": fid, "reason": reason, "models": {
            model_id: {"committed": item[1], "status": item[2], "reason": item[3],
                       "scored": evidence[model_id]}
            for model_id, item in ((base, b), (r.model_id, a))}})
    matched = matched_metrics(samples)
    n = matched["matched_n"]
    ll = None if n == 0 else (matched["models"][r.model_id]["log_loss"]
                                - matched["models"][base]["log_loss"])
    status = ("WINDOW_OPEN" if limit < p.evaluation_end else
              "INSUFFICIENT_MATCHED_SUPPORT" if n < p.min_matched else "SUFFICIENT_SYNTHETIC")
    result = {
        "version": COMPARISON_VERSION, "scope": "SYNTHETIC_PROSPECTIVE",
        "model_id": r.model_id, "baseline_id": base,
        "model_digest": r.model_digest, "config_digest": r.config_digest,
        "protocol_digest": r.protocol_digest, "dataset_digest": r.dataset_digest,
        "cohort_id": cohort.cohort_id, "cohort_digest": cohort.digest, "as_of": limit,
        "target_n": len(members), "models": models,
        "matched_n": n, "matched_keys": matched["matched_keys"],
        "matched_metrics": matched["models"],
        "matched_evidence": matched_evidence, "unmatched_evidence": unmatched_evidence,
        "unmatched_reasons": dict(sorted(reasons.items())),
        "ll_delta": ll, "status": status, "minimum_matched_n": p.min_matched,
        "uncertainty": "DESCRIPTIVE_ONLY",
    }
    return {**result, "digest": _digest(result)}


def candidate_comparison(conn: sqlite3.Connection, model_id: str, *, as_of: str):
    limit = utc_timestamp(as_of)
    with training_transaction(conn, write=False):
        return _comparison(conn, _stored_candidate(conn, model_id)[0], limit)


@dataclass(frozen=True)
class OwnerApproval:
    approval_id: str
    action: str
    from_model_id: str
    to_model_id: str
    model_digest: str
    config_digest: str
    evidence_digest: str
    decided_at: str
    approved: bool


@dataclass(frozen=True)
class PromotionEvent:
    event_id: str
    sequence: int
    approval_id: str
    action: str
    from_model_id: str
    to_model_id: str
    decided_at: str
    evidence_digest: str
    digest: str


def _approval(value):
    if type(value) is not OwnerApproval or value.approved is not True:
        raise ValueError("explicit typed synthetic owner approval required")
    for item in (value.approval_id, value.from_model_id, value.to_model_id):
        commitment._id(item)
    for item in (value.model_digest, value.config_digest, value.evidence_digest):
        require_digest(item)
    if value.action not in ("PROMOTE", "ROLLBACK") or value.from_model_id == value.to_model_id:
        raise ValueError("invalid lifecycle approval")
    return replace(value, decided_at=utc_timestamp(value.decided_at))


def _event_id(approval_id):
    return commitment._stable_id("lifecycle", LIFECYCLE_VERSION, approval_id)


def _validate_comparison_receipt(evidence, approval):
    if (type(evidence) is not dict or evidence.get("digest") != approval.evidence_digest
            or _digest({k: v for k, v in evidence.items() if k != "digest"}) != approval.evidence_digest
            or evidence.get("version") != COMPARISON_VERSION
            or evidence.get("scope") != "SYNTHETIC_PROSPECTIVE"
            or evidence.get("model_id") != approval.to_model_id
            or evidence.get("model_digest") != approval.model_digest
            or evidence.get("config_digest") != approval.config_digest
            or evidence.get("as_of") != approval.decided_at
            or evidence.get("status") != "SUFFICIENT_SYNTHETIC"):
        raise ValueError("promotion evidence mismatch")


def _chain(conn):
    """Read and verify append-only synthetic selection history, not old scores."""
    baseline = _baseline_version(conn)
    rows = conn.execute(
        "SELECT event_id,sequence,approval_id,action,from_model_id,to_model_id,"
        "decided_at,payload,digest FROM model_lifecycle_events ORDER BY sequence"
    ).fetchmany(MAX_EVENTS + 1)
    if len(rows) > MAX_EVENTS:
        raise ValueError("lifecycle history exceeds bound")
    events = []
    current = baseline.model_id
    previous = None
    for expected_seq, row in enumerate(rows, 1):
        eid, seq, aid, action, old, new, clock, raw, digest = row
        try:
            payload = json.loads(raw)
            a = _approval(OwnerApproval(**payload["approval"]))
            model = _version_for(conn, new)
            if (set(payload) != {"version", "scope", "sequence", "previous_digest", "approval", "evidence"}
                    or payload["version"] != LIFECYCLE_VERSION or payload["scope"] != "SYNTHETIC"
                    or commitment._json(payload) != raw or commitment._hash(raw) != digest
                    or payload["sequence"] != seq or seq != expected_seq
                    or payload["previous_digest"] != (previous.digest if previous else None)
                    or (a.approval_id, a.action, a.from_model_id, a.to_model_id, a.decided_at)
                       != (aid, action, old, new, clock)
                    or old != current or eid != _event_id(aid)
                    or (a.model_digest, a.config_digest) != (model.model_digest, model.config_digest)
                    or clock < model.created_at or clock < baseline.created_at
                    or (previous is not None and clock <= previous.decided_at)):
                raise ValueError("lifecycle chain mismatch")
            if action == "PROMOTE":
                if new == inference.MODEL_ID:
                    raise ValueError("baseline selection requires rollback")
                _validate_comparison_receipt(payload["evidence"], a)
            elif (previous is None or previous.action != "PROMOTE"
                  or new != previous.from_model_id or a.evidence_digest != previous.digest
                  or payload["evidence"] != {"rolled_back_event": previous.event_id,
                                              "digest": previous.digest}):
                raise ValueError("invalid rollback lineage")
        except (KeyError, TypeError, ValueError, IndexError):
            raise ValueError("invalid immutable lifecycle event") from None
        event = PromotionEvent(eid, seq, aid, action, old, new, clock, a.evidence_digest, digest)
        events.append((event, a))
        current, previous = new, event
    return current, tuple(events)


def active_model_id(conn: sqlite3.Connection) -> str:
    """Synthetic selection pointer only; never changes baseline API defaults."""
    with training_transaction(conn, write=False):
        return _chain(conn)[0]


def _replay(events, approval):
    for event, recorded in events:
        if event.approval_id == approval.approval_id:
            if recorded != approval:
                raise ValueError("conflicting immutable owner approval replay")
            return event
    return None


def _append_event(conn, current, events, approval, model, evidence):
    previous = events[-1][0] if events else None
    if (current != approval.from_model_id or model.model_id != approval.to_model_id
            or (model.model_digest, model.config_digest) != (approval.model_digest, approval.config_digest)
            or approval.decided_at < model.created_at
            or approval.decided_at < _baseline_version(conn).created_at
            or (previous is not None and approval.decided_at <= previous.decided_at)
            or len(events) >= MAX_EVENTS):
        raise ValueError("stale selection, model digest or approval clock")
    seq = len(events) + 1
    payload = {"version": LIFECYCLE_VERSION, "scope": "SYNTHETIC", "sequence": seq,
               "previous_digest": previous.digest if previous else None,
               "approval": asdict(approval), "evidence": evidence}
    raw = commitment._json(payload)
    digest = commitment._hash(raw)
    eid = _event_id(approval.approval_id)
    conn.execute("INSERT INTO model_lifecycle_events VALUES (?,?,?,?,?,?,?,?,?)",
                 (eid, seq, approval.approval_id, approval.action, current,
                  model.model_id, approval.decided_at, raw, digest))
    return PromotionEvent(eid, seq, approval.approval_id, approval.action, current,
                          model.model_id, approval.decided_at, approval.evidence_digest, digest)


def _check_no_later_cohort_evidence(conn, candidate, limit):
    # A new manual decision cannot ignore revisions already persisted with
    # later claimed clocks. Exact replay of an old decision is still safe.
    _, members = _cohort_for(conn, candidate)
    for member in members:
        if (conn.execute("SELECT 1 FROM result_versions WHERE match_id=? AND observed_at>? LIMIT 1",
                         (member["match_id"], limit)).fetchone()
                or conn.execute("SELECT 1 FROM fixture_versions WHERE match_id=? AND observed_at>? LIMIT 1",
                                (member["match_id"], limit)).fetchone()
                or conn.execute("SELECT 1 FROM evaluations e JOIN predictions p "
                                "ON p.prediction_id=e.prediction_id WHERE p.match_id=? "
                                "AND e.evaluated_at>? LIMIT 1", (member["match_id"], limit)).fetchone()):
            raise ValueError("approval predates already stored subsequent cohort evidence")


def promote_candidate(conn: sqlite3.Connection, model_id: str, approval: OwnerApproval, *, model_dir):
    """Manual synthetic selection; approval is a simulation input, not authentication."""
    a = _approval(approval)
    if a.action != "PROMOTE" or a.to_model_id != model_id or model_id == inference.MODEL_ID:
        raise ValueError("approval does not authorize this candidate")
    with training_transaction(conn, write=True):
        current, events = _chain(conn)
        replay = _replay(events, a)
        if replay is not None:
            return replay
        candidate = _load_candidate(conn, model_id, model_dir)
        _check_no_later_cohort_evidence(conn, candidate, a.decided_at)
        evidence = _comparison(conn, candidate, a.decided_at)
        _validate_comparison_receipt(evidence, a)
        return _append_event(conn, current, events, a, _model_version(candidate.receipt), evidence)


def rollback_promotion(conn: sqlite3.Connection, approval: OwnerApproval, *, model_dir):
    """Restore the predecessor of the last promotion for future selections."""
    a = _approval(approval)
    if a.action != "ROLLBACK":
        raise ValueError("rollback approval required")
    with training_transaction(conn, write=True):
        current, events = _chain(conn)
        replay = _replay(events, a)
        if replay is not None:
            return replay
        previous = events[-1][0] if events else None
        if (previous is None or previous.action != "PROMOTE"
                or a.to_model_id != previous.from_model_id
                or a.evidence_digest != previous.digest):
            raise ValueError("rollback must name the last promotion predecessor")
        if a.to_model_id == inference.MODEL_ID:
            model = _baseline_version(conn)
        else:
            model = _model_version(_load_candidate(conn, a.to_model_id, model_dir).receipt)
        return _append_event(conn, current, events, a, model,
                             {"rolled_back_event": previous.event_id, "digest": previous.digest})


def readiness_flag(new_eligible_n: int, *, last_check_at: str, as_of: str):
    last, limit = map(utc_timestamp, (last_check_at, as_of))
    if type(new_eligible_n) is not int or new_eligible_n < 0 or limit < last:
        raise ValueError("invalid operational readiness inputs")
    elapsed = datetime.fromisoformat(limit.replace("Z", "+00:00")) - datetime.fromisoformat(last.replace("Z", "+00:00"))
    return {"scope": "SYNTHETIC", "new_eligible_n": new_eligible_n,
            "last_check_at": last, "as_of": limit,
            "eligible_to_request": elapsed >= timedelta(days=7) and new_eligible_n >= 200,
            "manual_only": True, "statistical_power_claim": False}


def training_readiness(conn: sqlite3.Connection, *, last_check_at: str, as_of: str):
    last, limit = map(utc_timestamp, (last_check_at, as_of))
    if limit < last:
        raise ValueError("readiness clock reversed")
    with training_transaction(conn, write=False):
        previous = _previously_recorded_mature_matches(conn, last)
        current = _mature_match_ids(conn, limit)
        return readiness_flag(len(current - previous), last_check_at=last, as_of=limit)
