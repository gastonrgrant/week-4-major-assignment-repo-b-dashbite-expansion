from __future__ import annotations

import time

import altair as alt
import pandas as pd
import streamlit as st

from pipeline.config import load_config
from pipeline.paths import data_dirs
from pipeline.pulse import build_view


def _log_sources_once() -> None:
    if st.session_state.get("dashbite_logged"):
        return
    print("reading data/features and data/predictions", flush=True)
    st.session_state["dashbite_logged"] = True


def render() -> None:
    st.set_page_config(page_title="Model Pulse", layout="wide")
    _log_sources_once()
    dirs = data_dirs()
    view = build_view(dirs["raw"], dirs["features"], dirs["predictions"])

    st.title("Model Pulse")
    if view["checkpoint_id"]:
        st.caption(f"Scoring with {view['checkpoint_id']}")
    else:
        st.caption("Waiting for a checkpoint on disk")

    columns = st.columns(3)
    for column, kpi in zip(columns, view["kpis"]):
        column.metric(kpi["label"], kpi["value"])

    hero = view["hero"]
    st.subheader(hero["title"])
    if hero["points"]:
        st.line_chart(pd.DataFrame(hero["points"]), x="Minute", y="Orders")
    else:
        st.caption("No orders in this window yet")

    flags = view["flags"]
    st.subheader(flags["title"])
    if flags["points"]:
        st.line_chart(pd.DataFrame(flags["points"]), x="Minute", y="% flagged late")
    else:
        st.caption("No scored orders in this window yet")

    failures = view["failures"]
    st.subheader(failures["title"])
    if failures["bars"]:
        chart = (
            alt.Chart(pd.DataFrame(failures["bars"]))
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="Failed rows", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelAngle=0)),
            )
        )
        st.altair_chart(chart, use_container_width=True)

    time.sleep(load_config().poll_interval_seconds)
    st.rerun()


if __name__ == "__main__":
    render()
