"""Select immutable S5 examples, not retrospective feature recomputation."""
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
import json
import math
import sqlite3

from atp_lab.database.identity import utc_timestamp
from atp_lab.database.schema_v5 import training_transaction
from atp_lab.evaluation.eligibility import decide, fixture_info
from atp_lab.evaluation.service import _stored_assessment
from atp_lab.prediction import commitment, inference
from atp_lab.prediction.features import FEATURE_NAMES
from atp_lab.prediction.temporal import EMBARGO_DAYS
from .protocol import MAX_EXAMPLES, _read_protocol, canonical_day, midnight, require_digest

DATASET_VERSION = "S6_SYNTHETIC_DATASET_1"


@dataclass(frozen=True)
class TrainingExample:
    match_id: str
    event_id: str
    event_day: str
    fixture_id: str
    prediction_id: str
    commitment_digest: str
    feature_digest: str
    cutoff: str
    result_id: str
    history_result_ids: tuple[str, ...]
    values: tuple[tuple[str, int | float], ...]
    outcome_a: int
    assessment_id: str
    observed_at: str
    available_at: str
    evaluated_at: str
    actual_start: str
    published_at: str


@dataclass(frozen=True)
class TrainingDataset:
    protocol_digest: str
    fit: tuple[TrainingExample, ...]
    calibration: tuple[TrainingExample, ...]
    excluded: tuple[tuple[str, int], ...]

    @property
    def digest(self):
        return commitment._hash(commitment._json(dataset_payload(self)))


def dataset_payload(data):
    return {
        "version": DATASET_VERSION, "scope": "SYNTHETIC",
        "protocol_digest": data.protocol_digest,
        "fit": [asdict(row) for row in data.fit],
        "calibration": [asdict(row) for row in data.calibration],
        "excluded": data.excluded,
    }


def feature_vector(values):
    """Exact ordered finite 18-feature vector; no identity or label column."""
    if type(values) not in (tuple, list) or len(values) != len(FEATURE_NAMES):
        raise ValueError("wrong feature shape")
    out = []
    for name, item in zip(FEATURE_NAMES, values):
        if (type(item) not in (tuple, list) or len(item) != 2 or item[0] != name
                or type(item[1]) not in (float, int) or not math.isfinite(item[1])
                or abs(item[1]) > 1e12):
            raise ValueError("invalid feature name or value")
        out.append(float(item[1]))
    return tuple(out)


def _validate_example(row):
    if type(row) is not TrainingExample:
        raise ValueError("typed synthetic example required")
    for value in (row.match_id, row.event_id, row.fixture_id, row.prediction_id,
                  row.result_id, row.assessment_id):
        commitment._id(value)
    for value in (row.commitment_digest, row.feature_digest):
        require_digest(value)
    canonical_day(row.event_day)
    for clock in (row.cutoff, row.observed_at, row.available_at, row.evaluated_at,
                  row.actual_start, row.published_at):
        if utc_timestamp(clock) != clock:
            raise ValueError("noncanonical example clock")
    if (not row.cutoff < row.actual_start <= row.published_at <= row.observed_at
            <= row.available_at <= row.evaluated_at
            or row.event_day > row.actual_start[:10]
            or type(row.outcome_a) is not int or row.outcome_a not in (0, 1)
            or type(row.history_result_ids) is not tuple
            or len(set(row.history_result_ids)) != len(row.history_result_ids)
            or row.result_id in row.history_result_ids):
        raise ValueError("invalid example lineage or chronology")
    for rid in row.history_result_ids:
        commitment._id(rid)
    feature_vector(row.values)
    return row


def _mature(event_day, cutoff):
    return (date.fromisoformat(cutoff[:10]) - date.fromisoformat(event_day)).days >= EMBARGO_DAYS


def _partition(event_day, p):
    if p.fit_start <= event_day < p.fit_end:
        return "fit"
    if p.calibration_start <= event_day < p.calibration_end:
        return "calibration"
    return None


def _eligible_split(row, p, split):
    if _partition(row.event_day, p) != split:
        return False
    if split == "fit":
        deadline = midnight(p.calibration_start)
        return _mature(row.event_day, deadline) and row.evaluated_at < deadline
    return _mature(row.event_day, p.training_cutoff) and row.evaluated_at <= p.training_cutoff


def _order(row):
    return row.event_day, row.event_id, row.match_id, row.prediction_id


def validate_dataset(data, protocol, *, support=False):
    if (type(data) is not TrainingDataset or data.protocol_digest != protocol.digest
            or type(data.fit) is not tuple or type(data.calibration) is not tuple
            or len(data.fit) + len(data.calibration) > MAX_EXAMPLES
            or type(data.excluded) is not tuple):
        raise ValueError("invalid dataset identity or bounds")
    matches, events = set(), {}
    for split, rows in (("fit", data.fit), ("calibration", data.calibration)):
        if tuple(sorted(rows, key=_order)) != rows:
            raise ValueError("noncanonical training row order")
        for row in rows:
            _validate_example(row)
            if not _eligible_split(row, protocol, split) or row.match_id in matches:
                raise ValueError("duplicate match or temporal split violation")
            if events.setdefault(row.event_id, (row.event_day, split)) != (row.event_day, split):
                raise ValueError("event crosses chronological splits")
            matches.add(row.match_id)
    reasons = []
    for item in data.excluded:
        if (type(item) is not tuple or len(item) != 2 or type(item[0]) is not str
                or not item[0] or type(item[1]) is not int or item[1] < 1):
            raise ValueError("invalid dataset exclusion count")
        reasons.append(item[0])
    if reasons != sorted(set(reasons)):
        raise ValueError("noncanonical exclusion inventory")
    if support:
        if len(data.fit) < protocol.min_fit or len(data.calibration) < protocol.min_calibration:
            raise ValueError("insufficient synthetic fit/calibration support")
        if any({x.outcome_a for x in rows} != {0, 1} for rows in (data.fit, data.calibration)):
            raise ValueError("both canonical classes required in fit and calibration")
    return data


def decode_dataset(payload, protocol):
    try:
        def rows(key):
            out = []
            for row in payload[key]:
                item = dict(row)
                item["values"] = tuple(tuple(v) for v in item["values"])
                item["history_result_ids"] = tuple(item["history_result_ids"])
                out.append(TrainingExample(**item))
            return tuple(out)
        data = TrainingDataset(payload["protocol_digest"], rows("fit"), rows("calibration"),
                               tuple(tuple(v) for v in payload["excluded"]))
        validate_dataset(data, protocol, support=True)
        if commitment._json(dataset_payload(data)) != commitment._json(payload):
            raise ValueError("dataset payload mismatch")
        return data
    except (KeyError, TypeError, IndexError, ValueError, OverflowError):
        raise ValueError("invalid frozen training dataset") from None


def _baseline_commitments(conn, limit):
    rows = conn.execute(
        "SELECT prediction_id FROM predictions WHERE model_id=? AND created_at<=? "
        "ORDER BY created_at,prediction_id", (inference.MODEL_ID, limit)
    ).fetchmany(inference.MAX_ROWS + 1)
    if len(rows) > inference.MAX_ROWS:
        raise ValueError("baseline commitment inventory exceeds bound")
    for (pid,) in rows:
        try:
            c = commitment._get_commitment(conn, pid)
        except commitment.UnverifiedCommitment:
            yield None, None, None
            continue
        payload = json.loads(c.receipt_json)
        event_id = fixture_info(conn, c.prediction.fixture_id)["tournament_id"]
        metadata = [x for x in payload["events"] if x["tournament_id"] == event_id]
        if len(metadata) != 1:
            raise ValueError("invalid committed event metadata")
        day = canonical_day(metadata[0]["event_start"])
        yield c, event_id, day


def _example(conn, c, event_id, day, limit):
    decision = decide(conn, c, limit)
    stored = _stored_assessment(conn, c.prediction.prediction_id, decision, limit)
    if stored is None:
        return None, "NOT_EVALUATED"
    if stored.status != "RECORDED":
        return None, stored.reason
    if stored.evaluation_id is None or stored.evaluated_at is None:
        raise ValueError("missing stored evaluation evidence")
    result = conn.execute(
        "SELECT match_id,observed_at,available_at,actual_start,published_at "
        "FROM result_versions WHERE result_id=?", (stored.result_id,)).fetchone()
    if result is None or result[0] != c.prediction.match_id:
        raise ValueError("broken label lineage")
    payload = json.loads(c.receipt_json)["features"]
    ids = tuple(payload["result_ids"])
    # Original S4 receipt is authoritative; never rebuild features using
    # current result data. Explicitly reject current-match label references.
    for rid in ids:
        history = conn.execute("SELECT match_id FROM result_versions WHERE result_id=?",
                               (rid,)).fetchone()
        if history is None or history[0] == c.prediction.match_id:
            raise ValueError("missing history lineage or target leakage")
    row = TrainingExample(
        c.prediction.match_id, event_id, day, c.prediction.fixture_id,
        c.prediction.prediction_id, c.prediction.commitment_digest, c.feature.feature_digest,
        c.feature.cutoff, stored.result_id, ids, tuple(tuple(v) for v in payload["values"]),
        stored.outcome_a, stored.evaluation_id, result[1], result[2],
        stored.evaluated_at, result[3], result[4])
    return _validate_example(row), "ELIGIBLE"


def _collect(conn, p):
    groups = {"fit": [], "calibration": []}
    reasons = Counter()
    event_dates = {}
    for c, event_id, day in _baseline_commitments(conn, p.training_cutoff):
        if c is None:
            reasons["UNVERIFIED_COMMITMENT"] += 1
            continue
        split = _partition(day, p)
        if split is None:
            reasons["OUTSIDE_WINDOWS"] += 1
            continue
        if event_dates.setdefault(event_id, (day, split)) != (day, split):
            raise ValueError("event crosses chronological splits")
        row, reason = _example(conn, c, event_id, day, p.training_cutoff)
        if row is None:
            reasons[reason] += 1
        elif not _eligible_split(row, p, split):
            reasons["IMMATURE_OR_LATE_SPLIT_LABEL"] += 1
        else:
            groups[split].append(row)
            if len(groups["fit"]) + len(groups["calibration"]) > MAX_EXAMPLES:
                raise ValueError("synthetic training selection exceeds bound")
    data = TrainingDataset(p.digest, tuple(sorted(groups["fit"], key=_order)),
                           tuple(sorted(groups["calibration"], key=_order)),
                           tuple(sorted(reasons.items())))
    return validate_dataset(data, p)


def collect_dataset(conn: sqlite3.Connection, protocol_id: str) -> TrainingDataset:
    with training_transaction(conn, write=False):
        return _collect(conn, _read_protocol(conn, protocol_id))


def _mature_match_ids(conn, limit):
    matches = set()
    for c, event_id, day in _baseline_commitments(conn, limit):
        if c is None or not _mature(day, limit):
            continue
        row, _ = _example(conn, c, event_id, day, limit)
        if row is not None:
            if row.match_id in matches:
                raise ValueError("duplicate eligible match in readiness inventory")
            matches.add(row.match_id)
    return matches


def _previously_recorded_mature_matches(conn, limit):
    """Conservative prior inventory: a correction cannot make old evidence new.

    Count a baseline match already assessed as eligible by the checkpoint
    and mature at that checkpoint, even if its then-latest revision was
    unavailable. Current eligibility still uses the effective revision.
    """
    matches = set()
    for c, _, day in _baseline_commitments(conn, limit):
        if c is None or not _mature(day, limit):
            continue
        row = conn.execute(
            "SELECT 1 FROM evaluations e JOIN assessment_receipts a "
            "ON a.evaluation_id=e.evaluation_id JOIN result_versions r "
            "ON r.result_id=e.result_id WHERE e.prediction_id=? "
            "AND r.match_id=? AND e.status='RECORDED' AND a.reason='ELIGIBLE' "
            "AND a.outcome_a IN (0,1) AND e.evaluated_at<=? "
            "AND r.state='COMPLETED' AND r.observed_at<=e.evaluated_at "
            "AND r.available_at<=e.evaluated_at LIMIT 1",
            (c.prediction.prediction_id, c.prediction.match_id, limit)).fetchone()
        if row is not None:
            matches.add(c.prediction.match_id)
    return matches
