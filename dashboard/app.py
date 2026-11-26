"""Read-only V4 S1 Streamlit interface; no worker, provider, or training."""
from pathlib import Path

import pandas as pd
import streamlit as st

from atp_lab.historical import read_historical_evidence

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


def main():
    st.set_page_config(page_title="ATP Forecasting Lab", layout="wide")
    st.title("ATP Forecasting Lab")
    st.caption("V4.0 S1 | HISTORICAL DEVELOPMENT ONLY | Private offline research")
    page = st.sidebar.radio("Research workspace", PAGES)
    st.sidebar.caption("Real data and training: LOCKED")
    st.sidebar.caption("Read-only mode. No prospective validation claim.")

    if page != "Overview":
        st.header(page)
        st.info("LOCKED: " + LOCKED[page])
        st.caption("Historical evidence is available in Overview.")
        return

    try:
        view = read_historical_evidence(EVIDENCE)
    except ValueError:
        st.error("Historical evidence unavailable or invalid. Restore the exact pinned V3 evidence from the repository.")
        return

    st.header("Overview")
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


if __name__ == "__main__":
    main()
