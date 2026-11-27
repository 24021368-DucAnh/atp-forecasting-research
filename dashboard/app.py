"""Read-only local V4 interface; no worker, provider, or training starts here."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from atp_lab.dashboard.view import load_dashboard_view
from atp_lab.historical import read_historical_evidence
from atp_lab.worker.database import database_path, default_data_dir

EVIDENCE = (Path(__file__).resolve().parents[1] / "docs" / "research"
            / "p2_4_fixed_ablation_evidence_20261125.json")
PAGES = ("Overview", "Upcoming", "Tournaments", "Results", "Model Lab", "Data Health")
LOCKED = {
    "Upcoming": "Fixture ingestion is not authorized. No upcoming matches are available.",
    "Tournaments": "No current tournament feed is connected.",
    "Results": "No prospective forecasts have been committed or evaluated.",
    "Model Lab": "No operational model or training job is registered.",
    "Data Health": "Source authorization, ingestion, and worker monitoring are not active.",
}


def _show_historical_overview():
    try:
        view = read_historical_evidence(EVIDENCE)
    except ValueError:
        st.error("Historical evidence unavailable or invalid. Restore the exact pinned V3 evidence from the repository.")
        return

    cols = st.columns(4)
    cols[0].metric("Historical matches", f"{view['n']:,}")
    cols[1].metric("Historical candidates", str(len(view["models"])))
    cols[2].metric("Real data", "LOCKED")
    cols[3].metric("New predictions", "Unavailable")
    st.info("Historical results use previously inspected development years, not an untouched holdout or a current forecast.")
    st.subheader("Historical model comparison")
    names = sorted(view["models"])
    selected = st.multiselect("Models to compare", names, default=names)
    rows = []
    for name in selected:
        model = view["models"][name]
        rows.append({
            "Model": name,
            "Accuracy (%)": model["accuracy"] * 100,
            "Log loss": model["log_loss"],
            "Brier": model["brier"],
            "ECE": model["ece"],
            "Coverage (%)": model["coverage"] * 100,
            "Correct": model["correct"],
            "Matches": model["n"],
        })
    if rows:
        table = pd.DataFrame(rows)
        st.dataframe(table, hide_index=True, width="stretch")
        st.bar_chart(table.set_index("Model")["Accuracy (%)"])
    else:
        st.info("Select at least one historical candidate to compare.")
    st.caption("Accuracy selects A when p(A) >= 0.5, otherwise B. Lower log loss, Brier and ECE are better. Coverage refers to matched historical evaluation.")
    st.subheader("Historical evidence")
    st.write(" | ".join(f"{fold['year']}: {fold['n']:,} matches" for fold in view["folds"]))
    st.caption("P2.4 aggregate evidence; SHA-256 verified.")
    st.code(view["evidence_sha256"], language=None)


def _show_local_page(page: str, data_dir: Path):
    try:
        view = load_dashboard_view(database_path(data_dir), mode="SYNTHETIC_DEMO")
    except ValueError:
        st.error("The local database failed read-only verification. No records are shown.")
        return

    if view.database_state != "READY":
        st.info("No local workspace is initialized. Use the Windows setup command to create an empty database, then seed the synthetic demonstration explicitly.")
        return

    if page == "Overview":
        cols = st.columns(4)
        cols[0].metric("Local fixtures", str(view.overview["fixtures"]))
        cols[1].metric("Stored forecast rows", str(view.overview["predictions"]))
        cols[2].metric("Stored recorded rows", str(view.overview["scored"]))
        cols[3].metric("Real data", "LOCKED")
        st.info("This is a deterministic synthetic demonstration stored on this PC. It is not current ATP information or model validation.")
        st.caption("Stored counts may include legacy rows. Results labels a commitment or assessment only after its S5 receipt is verified.")
        st.caption(f"Worker: {view.health['worker_state']} · Scheduler: DISABLED · Network: DISABLED")
    elif page == "Upcoming":
        st.caption("Locally stored synthetic fixtures only. No live feed or refresh runs from this page.")
        if view.upcoming:
            rows = [{
                "Event": row["event"], "Edition": row["edition"],
                "Scheduled (UTC)": row["scheduled_start_utc"],
                "State": row["state"],
                "Player A": row["player_a"], "Player B": row["player_b"],
                "Forecast": row["forecast_state"],
                "P(Player A)": row["probability_a"],
            } for row in view.upcoming]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.info("There are no scheduled synthetic fixtures in this workspace.")
    elif page == "Tournaments":
        st.caption("Tournament identities come only from the local synthetic store.")
        if view.tournaments:
            rows = [{"Event": row["event"], "Edition": row["edition"],
                     "Tier": row["tier"], "Surface": row["surface"],
                     "Matches": row["match_count"]} for row in view.tournaments]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.info("No synthetic tournaments have been added.")
    elif page == "Results":
        st.caption("Assessment labels refer to the immutable assessed revision; HISTORICAL marks rows superseded by a later stored result revision.")
        if view.results:
            rows = [{
                "Event": f"{row['event']} {row['edition']}",
                "Match": f"{row['player_a']} vs {row['player_b']}",
                "Forecast": (f"{row['commitment_state']} · {row['probability_a']:.4f}"
                             if row["probability_a"] is not None else row["commitment_state"]),
                "Assessment": row["assessment_label"],
                "Result context": (
                    f"r{row['result_revision'] or '—'} → "
                    f"r{row['latest_result_revision'] or '—'} · "
                    f"{row['latest_result_state'] or 'No result yet'}"
                ),
                "Outcome A": row["outcome_a"],
            } for row in view.results]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.info("No local forecast records are available.")
    elif page == "Model Lab":
        st.metric("Displayed baseline", view.models["active_model_id"] or "Not registered")
        st.caption("Models are read-only here. Fitting, candidate promotion, and activation are not available in S7.")
        if view.models.get("versions"):
            rows = [{"Model": row["model_id"], "Scope": row["scope"],
                     "Training cutoff": row["training_cutoff"],
                     "Created": row["created_at"]}
                    for row in view.models["versions"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.metric("Registered training protocols", str(view.models["protocols"]))
    elif page == "Data Health":
        st.dataframe(pd.DataFrame([
            {"Check": "Database", "State": view.database_state},
            {"Check": "Worker", "State": view.health["worker_state"]},
            {"Check": "Last job", "State": str(view.health["last_job"] or "None")},
            {"Check": "Quality issues", "State": str(view.health["quality_issues"])},
            {"Check": "Database schema", "State": str(view.health["database_version"])},
            {"Check": "Real data access", "State": "LOCKED"},
            {"Check": "Scheduler", "State": "DISABLED"},
        ]), hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="ATP Forecasting Lab", layout="wide")
    st.title("ATP Forecasting Lab")
    st.caption("V4.0 S7 | OFFLINE LOCAL RESEARCH")
    mode = st.sidebar.radio("Data view", ("HISTORICAL", "SYNTHETIC_DEMO"),
                            format_func=lambda item: item.replace("_", " "))
    page = st.sidebar.radio("Research workspace", PAGES)
    st.sidebar.caption("Real data: LOCKED · Network: DISABLED")
    st.sidebar.caption("Training, scheduler, and model activation: DISABLED")
    st.header(page)

    if mode == "HISTORICAL":
        st.caption("HISTORICAL DEVELOPMENT ONLY · read-only pinned evidence")
        if page == "Overview":
            _show_historical_overview()
        else:
            st.info("LOCKED: " + LOCKED[page])
            st.caption("The historical evidence viewer is available in Overview.")
        return

    st.caption("SYNTHETIC DEMO · local fictional records · no network calls")
    root = os.environ.get("ATP_LAB_DATA_DIR")
    _show_local_page(page, Path(root) if root else default_data_dir())


if __name__ == "__main__":
    main()
