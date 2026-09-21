"""Milestone 7 — ad hoc exploration app. Sidebar filters (state, age band,
chronic condition, deceased/alive) drive three views: a filtered summary
table (by state), a cost distribution chart, and a condition-prevalence
chart. Backend (BigQuery or local DuckDB) is selected by the
STREAMLIT_BACKEND env var — see data_access.py.

Run locally: `make streamlit-run` (defaults to STREAMLIT_BACKEND=duckdb,
zero cloud cost, against the committed fixture sample).

See docs/IMPLEMENTATION_SPEC.md §16-17, §28 (Milestone 7).
"""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from data_access import CONDITION_COLUMNS, load_beneficiary_gold
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CONDITION_LABELS = {
    "has_alzheimers": "Alzheimer's / Dementia",
    "has_chf": "Congestive Heart Failure",
    "has_chronic_kidney_disease": "Chronic Kidney Disease",
    "has_cancer": "Cancer",
    "has_copd": "COPD",
    "has_depression": "Depression",
    "has_diabetes": "Diabetes",
    "has_ischemic_heart_disease": "Ischemic Heart Disease",
    "has_osteoporosis": "Osteoporosis",
    "has_rheumatoid_or_osteoarthritis": "Rheumatoid Arthritis / Osteoarthritis",
    "has_stroke_or_tia": "Stroke / TIA",
}

st.set_page_config(page_title="Medicare Claims Explorer", layout="wide")


@st.cache_data(show_spinner="Loading beneficiary data...")
def _load_data(backend: str) -> pd.DataFrame:
    return load_beneficiary_gold(backend)


def main() -> None:
    backend = os.environ.get("STREAMLIT_BACKEND", "duckdb")
    st.title("Medicare Claims Explorer")
    st.caption(f"CMS DE-SynPUF 2008 Beneficiary Summary File (synthetic data) — backend: `{backend}`")

    df = _load_data(backend)

    st.sidebar.header("Filters")
    states = st.sidebar.multiselect("State", sorted(df["state_abbr"].dropna().unique()), default=[])
    age_bands = st.sidebar.multiselect("Age band", ["Under 65", "65-74", "75-84", "85+"], default=[])
    condition_choices = st.sidebar.multiselect(
        "Chronic condition (any of)",
        options=CONDITION_COLUMNS,
        default=[],
        format_func=lambda col: CONDITION_LABELS[col],
    )
    deceased_choice = st.sidebar.radio("Status", ["All", "Alive", "Deceased"], index=0)

    filtered = df
    if states:
        filtered = filtered[filtered["state_abbr"].isin(states)]
    if age_bands:
        filtered = filtered[filtered["age_band"].isin(age_bands)]
    if condition_choices:
        filtered = filtered[filtered[condition_choices].any(axis=1)]
    if deceased_choice == "Alive":
        filtered = filtered[~filtered["is_deceased"]]
    elif deceased_choice == "Deceased":
        filtered = filtered[filtered["is_deceased"]]

    st.subheader(f"{len(filtered):,} beneficiaries match the current filters")

    col1, col2, col3 = st.columns(3)
    col1.metric("Beneficiaries", f"{len(filtered):,}")
    total_cost = filtered["total_medicare_reimbursement"].sum()
    col2.metric("Total Medicare-paid cost", f"${total_cost:,.0f}")
    avg_cost = filtered["total_medicare_reimbursement"].mean() if len(filtered) else 0
    col3.metric("Avg cost / beneficiary", f"${avg_cost:,.0f}")

    st.markdown("#### Summary by state")
    if filtered.empty:
        st.info("No beneficiaries match the current filters.")
    else:
        summary = (
            filtered.groupby(["state_abbr", "state_name"], as_index=False)
            .agg(
                beneficiary_count=("desynpuf_id", "count"),
                total_cost=("total_medicare_reimbursement", "sum"),
                avg_cost=("total_medicare_reimbursement", "mean"),
            )
            .sort_values("beneficiary_count", ascending=False)
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("#### Cost distribution")
        if filtered.empty:
            st.info("No data to chart.")
        else:
            cost_chart = (
                alt.Chart(filtered)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "total_medicare_reimbursement:Q", bin=alt.Bin(maxbins=40), title="Total Medicare-paid cost ($)"
                    ),
                    y=alt.Y("count():Q", title="Beneficiaries"),
                )
            )
            st.altair_chart(cost_chart, use_container_width=True)

    with chart_col2:
        st.markdown("#### Chronic condition prevalence")
        if filtered.empty:
            st.info("No data to chart.")
        else:
            prevalence = pd.DataFrame(
                {
                    "condition": [CONDITION_LABELS[c] for c in CONDITION_COLUMNS],
                    "prevalence": [filtered[c].mean() for c in CONDITION_COLUMNS],
                }
            )
            prevalence_chart = (
                alt.Chart(prevalence)
                .mark_bar()
                .encode(
                    x=alt.X("prevalence:Q", axis=alt.Axis(format="%"), title="Prevalence"),
                    y=alt.Y("condition:N", sort="-x", title=None),
                )
            )
            st.altair_chart(prevalence_chart, use_container_width=True)


if __name__ == "__main__":
    main()
