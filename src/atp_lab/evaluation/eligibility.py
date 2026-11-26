"""Conservative as-of eligibility for one committed synthetic prediction."""
from dataclasses import dataclass
import json

from atp_lab.database.identity import utc_timestamp
from atp_lab.prediction.commitment import _id
from atp_lab.prediction.inference import MAX_ROWS


@dataclass(frozen=True)
class Assessment:
    status: str
    reason: str
    result_id: str | None = None
    outcome_a: int | None = None
    evaluation_id: str | None = None
    evaluated_at: str | None = None


def _clock(value):
    if utc_timestamp(value) != value:
        raise ValueError("noncanonical persisted clock")
    return value


def _optional_clock(value):
    return None if value is None else _clock(value)


def fixture_info(conn, fixture_id):
    _id(fixture_id)
    row = conn.execute(
        "SELECT f.fixture_id,f.match_id,f.source_id,f.revision,f.player_a,f.player_b,"
        "f.observed_at,f.available_at,f.scheduled_start,f.state,m.tournament_id,"
        "m.canonical_a,m.canonical_b,t.tier,t.surface,s.mode,s.permission_status "
        "FROM fixture_versions f JOIN matches m ON m.match_id=f.match_id "
        "JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "JOIN data_sources s ON s.source_id=f.source_id WHERE f.fixture_id=?",
        (fixture_id,)).fetchone()
    if row is None or tuple(row[4:6]) != tuple(row[11:13]) or tuple(row[15:]) != ("SYNTHETIC", "LOCKED"):
        raise ValueError("unverified fixture identity")
    keys = ("fixture_id", "match_id", "source_id", "revision", "player_a", "player_b",
            "observed_at", "available_at", "scheduled_start", "state", "tournament_id",
            "canonical_a", "canonical_b", "tier", "surface", "mode", "permission")
    out = dict(zip(keys, row))
    for key in ("fixture_id", "match_id", "source_id", "player_a", "player_b", "tournament_id"):
        _id(out[key])
    _clock(out["observed_at"])
    _optional_clock(out["available_at"])
    _optional_clock(out["scheduled_start"])
    return out


def fixture_eligible(info, cutoff):
    return (info["state"] == "SCHEDULED"
            and info["surface"] in ("HARD", "CLAY", "GRASS")
            and info["available_at"] is not None
            and info["scheduled_start"] is not None
            and info["observed_at"] <= info["available_at"] <= cutoff < info["scheduled_start"])


def decide(conn, commitment, as_of):
    """Pure as-of decision. Pending or source ambiguity has no terminal row."""
    p = commitment.prediction
    if as_of < p.created_at:
        raise ValueError("evaluation precedes commitment")
    info = fixture_info(conn, p.fixture_id)
    if info["match_id"] != p.match_id or not fixture_eligible(info, p.created_at):
        raise ValueError("invalid committed fixture lineage")
    rows = conn.execute(
        "SELECT result_id,source_id,revision,observed_at,available_at,published_at,"
        "actual_start,state,winner FROM result_versions WHERE match_id=? "
        "AND observed_at<=? ORDER BY revision DESC,result_id",
        (p.match_id, as_of)).fetchmany(MAX_ROWS + 1)
    if len(rows) > MAX_ROWS:
        raise ValueError("result revision inventory exceeds bound")
    if not rows:
        return Assessment("PENDING", "NO_RESULT")
    if len({row[1] for row in rows}) != 1:
        return Assessment("INELIGIBLE", "AMBIGUOUS_RESULT_SOURCE")
    rid, source, _, observed, available, published, actual, state, winner = rows[0]
    _id(rid)
    if source != info["source_id"]:
        return Assessment("INELIGIBLE", "RESULT_SOURCE_MISMATCH")
    observed = _clock(observed)
    available, published, actual = map(_optional_clock, (available, published, actual))
    if available is None or available > as_of:
        return Assessment("PENDING", "RESULT_UNAVAILABLE", rid)
    if (available < observed or (published is not None and published > observed)
            or (actual is not None and actual > observed)
            or (actual is not None and published is not None and actual > published)):
        raise ValueError("invalid persisted result chronology")
    # A later correction cannot erase an earlier observation at/before commitment.
    if any(_clock(row[3]) <= p.created_at for row in rows):
        return Assessment("INELIGIBLE", "RESULT_OBSERVED_BEFORE_COMMIT", rid)
    if state in ("VOID", "WALKOVER"):
        return Assessment("VOID", "VOID_RESULT" if state == "VOID" else "WALKOVER", rid)
    if state in ("RETIRED", "UNKNOWN"):
        return Assessment("INELIGIBLE", "RETIRED" if state == "RETIRED" else "UNKNOWN_RESULT", rid)
    if state != "COMPLETED" or winner not in (info["player_a"], info["player_b"]):
        return Assessment("INELIGIBLE", "INVALID_OUTCOME", rid)
    if actual is None or published is None:
        return Assessment("INELIGIBLE", "UNVERIFIED_TIMING", rid)
    if not p.created_at < actual <= published <= observed <= available <= as_of:
        return Assessment("INELIGIBLE", "LATE_PREDICTION", rid)
    # The event-start clock is frozen in the commitment, never inferred
    # from the scheduled match. A contradictory actual date is not scored.
    metadata = json.loads(commitment.receipt_json)["events"]
    event_dates = [x["event_start"] for x in metadata if x["tournament_id"] == info["tournament_id"]]
    if len(event_dates) != 1 or actual[:10] < event_dates[0]:
        return Assessment("INELIGIBLE", "UNVERIFIED_TIMING", rid)
    if conn.execute(
        "SELECT 1 FROM fixture_versions WHERE match_id=? AND observed_at<=? "
        "AND (source_id<>? OR revision>?) LIMIT 1",
        (p.match_id, actual, info["source_id"], info["revision"])).fetchone():
        return Assessment("INELIGIBLE", "FIXTURE_SUPERSEDED", rid)
    return Assessment("RECORDED", "ELIGIBLE", rid, int(winner == info["player_a"]))
