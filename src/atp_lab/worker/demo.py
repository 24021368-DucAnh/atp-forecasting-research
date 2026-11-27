"""Deterministic, explicitly synthetic offline dashboard demonstration."""

from contextlib import closing
from datetime import date
from hashlib import sha256
from pathlib import Path

from atp_lab.database import forecast, identity
from atp_lab.database.connection import open_writer
from atp_lab.database.schema_v3 import verify_forecast_schema
from atp_lab.evaluation.service import evaluate_prediction, register_cohort
from atp_lab.prediction import commitment, inference

SOURCE = "SYN-demo-feed"
MODEL = inference.MODEL_ID


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _put_match(conn, *, key, edition, event_start, observed, scheduled, pair):
    match_id = f"SYN-demo-match-{key}"
    fixture_id = f"SYN-demo-fixture-{key}"
    snapshot_id = f"SYN-demo-snapshot-{key}"
    conn.execute("BEGIN IMMEDIATE")
    identity.put_tournament(conn, identity.Tournament(
        f"SYN-demo-tournament-{key}", f"SYN-demo-event-{key}", edition, "ATP250", "HARD"))
    identity.put_match(conn, identity.Match(match_id, f"SYN-demo-tournament-{key}", *pair))
    identity.put_snapshot(conn, identity.Snapshot(
        snapshot_id, SOURCE, _digest(snapshot_id), observed))
    identity.append_fixture(conn, identity.Fixture(
        fixture_id, match_id, 1, SOURCE, snapshot_id, *pair,
        observed, observed, scheduled, "SCHEDULED"))
    conn.commit()
    event = inference.EventMetadata(
        f"SYN-demo-tournament-{key}", 1, date.fromisoformat(event_start), observed, observed)
    return fixture_id, match_id, event


def _append_result(conn, *, key, match_id, observed, available, published,
                   actual_start, winner):
    result_id = f"SYN-demo-result-{key}"
    snapshot_id = f"SYN-demo-snapshot-result-{key}"
    conn.execute("BEGIN IMMEDIATE")
    identity.put_snapshot(conn, identity.Snapshot(
        snapshot_id, SOURCE, _digest(snapshot_id), observed))
    identity.append_result(conn, identity.Result(
        result_id, match_id, 1, SOURCE, snapshot_id, observed, available,
        published, actual_start, "COMPLETED", winner))
    conn.commit()


def seed_demo(database: Path) -> dict[str, int | str]:
    """Create one scored commitment and one future synthetic fixture, idempotently."""
    with closing(open_writer(database)) as conn:
        verify_forecast_schema(conn)
        demo_fixtures = ("SYN-demo-fixture-history", "SYN-demo-fixture-scored",
                         "SYN-demo-fixture-upcoming")
        placeholders = ",".join("?" for _ in demo_fixtures)
        counts = {
            "fixtures": conn.execute(
                f"SELECT count(*) FROM fixture_versions WHERE fixture_id IN ({placeholders})",
                demo_fixtures).fetchone()[0],
            "predictions": conn.execute(
                f"SELECT count(*) FROM predictions WHERE fixture_id IN ({placeholders})",
                demo_fixtures).fetchone()[0],
            "results": conn.execute(
                "SELECT count(*) FROM result_versions WHERE result_id IN "
                "('SYN-demo-result-history','SYN-demo-result-scored')").fetchone()[0],
            "scored": conn.execute(
                "SELECT count(*) FROM evaluations e JOIN predictions p "
                "ON p.prediction_id=e.prediction_id WHERE p.fixture_id=? AND e.status='RECORDED'",
                ("SYN-demo-fixture-scored",)).fetchone()[0],
        }
        present = sum(counts.values())
        if counts == {"fixtures": 3, "predictions": 2, "results": 2, "scored": 1}:
            prediction_id = conn.execute(
                "SELECT prediction_id FROM predictions WHERE fixture_id=?",
                ("SYN-demo-fixture-upcoming",)).fetchone()[0]
            return {"fixtures": 3, "predictions": 2, "scored": 1,
                    "upcoming_prediction_id": prediction_id}
        if present:
            raise ValueError("synthetic demonstration is partially seeded; refusing to modify it")

        conn.execute("BEGIN IMMEDIATE")
        identity.put_source(conn, identity.Source(SOURCE, "SYNTHETIC", "LOCKED"))
        for player in ("SYN-demo-A", "SYN-demo-B", "SYN-demo-C"):
            identity.put_player(conn, identity.Player(player))
        forecast.append_model(conn, inference.synthetic_model_version(
            created_at="2024-01-01T00:00:00Z"))
        conn.commit()

        _, history_match, history_event = _put_match(
            conn, key="history", edition="2024",
            event_start="2024-01-10", observed="2024-01-01T09:00:00Z",
            scheduled="2024-01-10T14:00:00Z",
            pair=("SYN-demo-A", "SYN-demo-B"),
        )
        _append_result(conn, key="history", match_id=history_match,
                       observed="2024-01-10T17:00:00Z", available="2024-01-10T18:00:00Z",
                       published="2024-01-10T16:00:00Z", actual_start="2024-01-10T14:00:00Z",
                       winner="SYN-demo-B")
        past_fixture, past_match, past_event = _put_match(
            conn, key="scored", edition="2025",
            event_start="2025-03-10", observed="2025-03-01T09:00:00Z",
            scheduled="2025-03-10T14:00:00Z",
            pair=("SYN-demo-A", "SYN-demo-C"),
        )
        future_fixture, _, future_event = _put_match(
            conn, key="upcoming", edition="2027",
            event_start="2027-01-12", observed="2025-03-01T09:00:00Z",
            scheduled="2027-01-12T14:00:00Z",
            pair=("SYN-demo-B", "SYN-demo-C"),
        )
        events = (history_event, past_event, future_event)
        register_cohort(
            conn, "SYN-demo-cohort", (past_fixture, future_fixture), (MODEL,),
            registered_at="2025-03-08T12:00:00Z", cutoff_end="2027-02-01T00:00:00Z",
        )
        scored = commitment.commit_prediction(
            conn, past_fixture, events, cutoff="2025-03-09T12:00:00Z",
            created_at="2025-03-09T12:00:00Z", model_id=MODEL,
        )
        upcoming = commitment.commit_prediction(
            conn, future_fixture, events, cutoff="2026-11-26T12:00:00Z",
            created_at="2026-11-26T12:00:00Z", model_id=MODEL,
        )
        _append_result(conn, key="scored", match_id=past_match,
                       observed="2025-03-10T17:00:00Z", available="2025-03-10T18:00:00Z",
                       published="2025-03-10T16:00:00Z", actual_start="2025-03-10T14:00:00Z",
                       winner="SYN-demo-A")
        assessment = evaluate_prediction(
            conn, scored.prediction.prediction_id, as_of="2025-03-11T12:00:00Z")
        if assessment.status != "RECORDED":
            raise ValueError("synthetic demonstration assessment was not eligible")
        return {"fixtures": 3, "predictions": 2, "scored": 1,
                "upcoming_prediction_id": upcoming.prediction.prediction_id}
