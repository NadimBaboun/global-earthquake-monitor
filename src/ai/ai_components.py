import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import re
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.ai_utils import SeismicAI

from constants import ALERT_HEX_COLORS
from utils.chart_utils import render_plotly_chart

logger = logging.getLogger(__name__)


def build_ai_chart(chart_spec: dict, base_df: pd.DataFrame) -> go.Figure | None:
    """Build a Plotly figure from a parsed CHART spec, with its own independent filters."""
    import plotly.express as px

    c_type = chart_spec.get("type", "bar").strip()
    c_title = chart_spec.get("title", "AI Generated Chart").strip()
    c_x = chart_spec.get("x", "").strip() or None
    c_y = chart_spec.get("y", "").strip() or None
    c_color = chart_spec.get("color", "").strip() or None
    f_alert = chart_spec.get("filter_alert", "").strip() or None
    f_country = chart_spec.get("filter_country", "").strip() or None

    # Apply chart-specific filters independently
    chart_df = base_df.copy()
    if f_alert:
        alerts = [a.strip().lower() for a in f_alert.split("|")]
        chart_df = chart_df[chart_df["alert_level"].str.lower().isin(alerts)]
    if f_country:
        countries = [c.strip().lower() for c in f_country.split("|")]
        chart_df = chart_df[chart_df["country"].str.lower().isin(countries)]

    if chart_df.empty:
        return None

    # Coerce numeric columns
    numeric_cols = {
        "magnitude",
        "depth_km",
        "sig",
        "felt",
        "tsunami",
        "alert_score",
        "latitude",
        "longitude",
    }
    for col in [c_x, c_y]:
        if col and col in chart_df.columns and col in numeric_cols:
            chart_df[col] = pd.to_numeric(chart_df[col], errors="coerce")

    # Auto-aggregate for count-based charts
    valid_cols = chart_df.columns.tolist()
    if c_y and (c_y in ("count", "1") or c_y not in valid_cols):
        if c_x and c_x in valid_cols:
            chart_df = chart_df.groupby(c_x).size().reset_index(name="count")
            c_y = "count"

    try:
        if c_type == "scatter":
            return px.scatter(
                chart_df,
                x=c_x,
                y=c_y,
                color=c_color,
                title=c_title,
                color_discrete_map=ALERT_HEX_COLORS,
            )
        elif c_type == "bar":
            return px.bar(
                chart_df,
                x=c_x,
                y=c_y,
                color=c_color,
                title=c_title,
                color_discrete_map=ALERT_HEX_COLORS,
            )
        elif c_type == "pie":
            if c_y and c_y not in chart_df.columns and c_x and c_x in chart_df.columns:
                pie_df = chart_df[c_x].value_counts().reset_index()
                pie_df.columns = [c_x, "count"]
                return px.pie(
                    pie_df,
                    names=c_x,
                    values="count",
                    title=c_title,
                    color_discrete_map=ALERT_HEX_COLORS,
                )
            return px.pie(
                chart_df,
                names=c_x,
                values=c_y,
                title=c_title,
                color_discrete_map=ALERT_HEX_COLORS,
            )
        elif c_type == "histogram":
            return px.histogram(
                chart_df,
                x=c_x,
                color=c_color,
                title=c_title,
                color_discrete_map=ALERT_HEX_COLORS,
            )
        elif c_type == "line":
            return px.line(chart_df, x=c_x, y=c_y, color=c_color, title=c_title)
        elif c_type == "box":
            return px.box(
                chart_df,
                x=c_x,
                y=c_y,
                color=c_color,
                title=c_title,
                color_discrete_map=ALERT_HEX_COLORS,
            )
    except Exception:
        pass
    return None


def render_ai_chat(
    filtered_df: pd.DataFrame, ai_engine: "SeismicAI", key_suffix: str = ""
) -> None:
    """Renders the AI chat interface."""
    st.subheader("Seismic Assistant")

    if "ai_chart_counter" not in st.session_state:
        st.session_state.ai_chart_counter = 0

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            for spec in message.get("chart_specs", []):
                fig = build_ai_chart(spec, filtered_df)
                if fig:
                    st.session_state.ai_chart_counter += 1
                    render_plotly_chart(
                        fig, key=f"ai_hist_chart_{st.session_state.ai_chart_counter}"
                    )

    input_key = f"ai_chat_input_{key_suffix}"
    if user_input := st.chat_input(
        "Ask me anything about earthquakes...", key=input_key
    ):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            context = ai_engine.generate_context_from_df(filtered_df)
            response = ai_engine.get_ai_response(
                user_input, context, st.session_state.chat_history
            )

            nav_tab = None
            date_update = None
            source_update = None
            alert_update = None
            country_update = None
            chart_specs = []

            for m in re.finditer(r"\[\[NAVIGATE:\s*(.*?)\]\]", response):
                nav_tab = m.group(1).strip()
                response = response.replace(m.group(0), "").strip()
            for m in re.finditer(r"\[\[SET_DATE:\s*(.*?),\s*(.*?)\]\]", response):
                try:
                    from datetime import datetime as dt

                    date_update = (
                        dt.strptime(m.group(1).strip(), "%Y-%m-%d").date(),
                        dt.strptime(m.group(2).strip(), "%Y-%m-%d").date(),
                    )
                    response = response.replace(m.group(0), "").strip()
                except Exception:
                    pass
            for m in re.finditer(r"\[\[SET_SOURCE:\s*(.*?)\]\]", response):
                source_update = m.group(1).strip()
                response = response.replace(m.group(0), "").strip()
            for m in re.finditer(r"\[\[SET_ALERT:\s*(.*?)\]\]", response):
                alert_update = [x.strip() for x in m.group(1).split(",")]
                response = response.replace(m.group(0), "").strip()
            for m in re.finditer(r"\[\[SET_COUNTRY:\s*(.*?)\]\]", response):
                country_update = [x.strip() for x in m.group(1).split(",")]
                response = response.replace(m.group(0), "").strip()
            for m in re.finditer(r"\[\[CHART:\s*(.*?)\]\]", response, re.DOTALL):
                spec = {}
                for item in m.group(1).split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        spec[k.strip()] = v.strip()
                chart_specs.append(spec)
                response = response.replace(m.group(0), "").strip()

            st.markdown(response.strip())
            for spec in chart_specs:
                fig = build_ai_chart(spec, filtered_df)
                if fig:
                    st.session_state.ai_chart_counter += 1
                    render_plotly_chart(
                        fig,
                        key=f"ai_chart_{key_suffix}_{st.session_state.ai_chart_counter}",
                    )
                else:
                    logger.info('No data available for AI chart: "%s"', spec.get("title", "chart"))

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": response.strip(),
                    "chart_specs": chart_specs,
                }
            )

            if any([nav_tab, date_update, source_update, alert_update, country_update]):
                if nav_tab:
                    st.session_state.active_tab = nav_tab
                    st.session_state.pending_nav_update = nav_tab
                if date_update:
                    st.session_state.pending_date_update = date_update
                pending = st.session_state.get("pending_filter_updates", {})
                if source_update:
                    pending["source_select"] = source_update
                if alert_update:
                    pending["alert_multiselect"] = alert_update
                if country_update:
                    pending["country_multiselect"] = country_update
                if pending:
                    st.session_state.pending_filter_updates = pending
                st.rerun()
