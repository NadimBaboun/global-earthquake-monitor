import os
import pandas as pd
import streamlit as st
import logging
from datetime import datetime, timezone, timedelta
from data import CONFIG, load_data_by_source
from config import UI_CONFIG
from chart_utils import render_plotly_chart
import plotly.express as px
import plotly.graph_objects as go
from constants import ALERT_HEX_COLORS
from map_utils import render_earthquake_map
from components import inject_custom_css, render_significant_quakes_table
from ai_utils import SeismicAI

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Global Earthquake Monitor (USGS)", page_icon="🌍", layout="wide")

# Inject custom styling for metrics and tables
inject_custom_css()

# ---------- AI Setup ----------
ai = SeismicAI()

# Handle any pending AI-driven updates BEFORE widgets are instantiated
if "pending_date_update" in st.session_state:
    update = st.session_state.pop("pending_date_update")
    st.session_state.date_range = update
    st.session_state.date_picker = update

# Handle any pending filter updates (Source, Alert, Country)
if "pending_filter_updates" in st.session_state:
    updates = st.session_state.pop("pending_filter_updates")
    for key, value in updates.items():
        st.session_state[key] = value

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Overview"

today_utc = datetime.now(timezone.utc).date()
default_start = today_utc - timedelta(days=UI_CONFIG["default_days_back"])

if "date_range" not in st.session_state:
    st.session_state.date_range = (default_start, today_utc)

if "date_picker" not in st.session_state:
    st.session_state.date_picker = (default_start, today_utc)

# ---------- UI ----------
st.title("Global Earthquake Monitor — Live Dashboard")

# Sidebar: date range picker (drives the API query)
st.sidebar.header("Data Source (UTC)")
source_label = st.sidebar.radio("Source", ["USGS", "GDACS", "Both"], index=0, horizontal=True, key="source_select")

# Date range picker synced with session state
date_range = st.sidebar.date_input("Date range", key="date_picker")
st.session_state.date_range = date_range

# date_input returns a single date while the user is mid-selection; guard against that
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = default_start, today_utc

min_mag = st.sidebar.slider(
    "Minimum magnitude",
    min_value=1.0, max_value=8.0,
    value=CONFIG["default_min_magnitude"],
    step=0.5,
)
# Auto-refresh checkbox removed due to navigation performance issues.

# Fetch data using the selected date range and magnitude
from_str = start_d.strftime("%Y-%m-%d")
to_str = end_d.strftime("%Y-%m-%d")

df, warn = load_data_by_source(
    from_date=from_str,
    to_date=to_str,
    min_magnitude=min_mag,
    source=source_label,
)
last_updated_utc = datetime.now(timezone.utc)
st.sidebar.caption(f"Last updated: {last_updated_utc.strftime('%Y-%m-%d %H:%M UTC')}")
if warn:
    st.warning(warn)

if df is None or df.empty:
    st.error("No earthquake data available for the selected criteria.")
    st.stop()

# XML download button
xml_path = CONFIG["xml_output_file"]
if source_label in {"USGS", "Both"} and os.path.exists(xml_path):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml_content = f.read()
    st.sidebar.download_button(
        label="📥 Download XML (QuakeML)",
        data=xml_content,
        file_name="earthquakes.xml",
        mime="application/xml",
    )

# Sidebar filters
st.sidebar.header("Filters")

all_levels = sorted([x for x in df["alert_level"].dropna().unique().tolist() if x])
all_countries = sorted([x for x in df["country"].dropna().unique().tolist() if x])

selected_levels = st.sidebar.multiselect("Alert level", all_levels, default=all_levels, key="alert_multiselect")
selected_countries = st.sidebar.multiselect("Country / Region", all_countries, default=all_countries, key="country_multiselect")
tsunami_only = st.sidebar.checkbox("Show only tsunami advisories", value=False)

max_points = st.sidebar.slider(
    "Map points",
    UI_CONFIG["map_points_min"],
    UI_CONFIG["map_points_max"],
    UI_CONFIG["map_points_default"],
    UI_CONFIG["map_points_min"],
)

# Apply filters
mask = (
    df["alert_level"].isin(selected_levels)
    & df["country"].isin(selected_countries)
    & df["date_utc"].between(start_d, end_d)
)
filtered = df.loc[mask].copy()

if "tsunami" in filtered.columns:
    filtered["tsunami"] = pd.to_numeric(filtered["tsunami"], errors="coerce").fillna(0).astype(int)
else:
    filtered["tsunami"] = 0

if tsunami_only:
    filtered = filtered[filtered["tsunami"] == 1]

if filtered.empty:
    st.warning("No records match your filters.")
    st.stop()

# Quick-glance metrics
st.sidebar.subheader("Summary")

avg_mag = pd.to_numeric(filtered["magnitude"], errors="coerce").mean()
max_mag = pd.to_numeric(filtered["magnitude"], errors="coerce").max()

m1, m2, m3 = st.sidebar.columns(3)
m1.metric("Quakes", int(len(filtered)))
m2.metric("Avg Mag", round(float(avg_mag), 1) if pd.notna(avg_mag) else "N/A")
m3.metric("Max Mag", round(float(max_mag), 1) if pd.notna(max_mag) else "N/A")
tsunami_count = int((filtered["tsunami"] == 1).sum()) if "tsunami" in filtered.columns else 0
st.sidebar.metric("Tsunami Advisories", tsunami_count)

# Pre-compute daily aggregates for graphs
daily_count = filtered.groupby("date_utc").size()
daily_avg_mag = filtered.groupby("date_utc")["magnitude"].mean()
cumulative_quakes = daily_count.cumsum()

# Daily summary table
st.sidebar.subheader("Daily summary")
show_all_days = st.sidebar.checkbox("Show all days", value=True)

summary_tbl = pd.DataFrame(
    {
        "date_utc": daily_count.index,
        "quakes": daily_count.values,
        "avg_magnitude": daily_avg_mag.reindex(daily_count.index).values,
    }
).reset_index(drop=True)

if not show_all_days:
    summary_tbl = summary_tbl.tail(10)

summary_tbl.index = range(1, len(summary_tbl) + 1)

st.sidebar.dataframe(
    summary_tbl,
    width="stretch",
    height=UI_CONFIG["sidebar_table_height"],
)

# ---------- AI Chart Renderer ----------
def build_ai_chart(chart_spec: dict, base_df: pd.DataFrame) -> "go.Figure | None":
    """Build a Plotly figure from a parsed CHART spec, with its own independent filters."""

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

    # Only coerce columns that should actually be numeric (not categories like country, alert_level)
    numeric_cols = {"magnitude", "depth_km", "sig", "felt", "tsunami", "alert_score", "latitude", "longitude"}
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
            return px.scatter(chart_df, x=c_x, y=c_y, color=c_color, title=c_title,
                              color_discrete_map=ALERT_HEX_COLORS)
        elif c_type == "bar":
            return px.bar(chart_df, x=c_x, y=c_y, color=c_color, title=c_title,
                          color_discrete_map=ALERT_HEX_COLORS)
        elif c_type == "pie":
            if c_y and c_y not in chart_df.columns and c_x and c_x in chart_df.columns:
                pie_df = chart_df[c_x].value_counts().reset_index()
                pie_df.columns = [c_x, "count"]
                return px.pie(pie_df, names=c_x, values="count", title=c_title,
                              color_discrete_map=ALERT_HEX_COLORS)
            return px.pie(chart_df, names=c_x, values=c_y, title=c_title,
                          color_discrete_map=ALERT_HEX_COLORS)
        elif c_type == "histogram":
            return px.histogram(chart_df, x=c_x, color=c_color, title=c_title,
                                color_discrete_map=ALERT_HEX_COLORS)
        elif c_type == "line":
            return px.line(chart_df, x=c_x, y=c_y, color=c_color, title=c_title)
        elif c_type == "box":
            return px.box(chart_df, x=c_x, y=c_y, color=c_color, title=c_title,
                          color_discrete_map=ALERT_HEX_COLORS)
    except Exception as e:
        logger.error(f"build_ai_chart error ({c_type}): {e}")
    return None


# ---------- AI Chat Component ----------
def render_ai_chat(filtered_df, key_suffix=""):
    """Renders the AI chat interface. filtered_df is the current dashboard-filtered data."""
    import re
    st.subheader("Seismic Assistant")

    if "ai_chart_counter" not in st.session_state:
        st.session_state.ai_chart_counter = 0

    # Display chat history — re-render charts that were stored alongside messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Re-render any charts attached to this message
            for spec in message.get("chart_specs", []):
                fig = build_ai_chart(spec, filtered_df)
                if fig:
                    st.session_state.ai_chart_counter += 1
                    render_plotly_chart(fig, key=f"ai_hist_chart_{st.session_state.ai_chart_counter}")

    input_key = f"ai_chat_input_{key_suffix}"
    if user_input := st.chat_input("Ask me anything about earthquakes...", key=input_key):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            context = ai.generate_context_from_df(filtered_df)
            response = ai.get_ai_response(user_input, context, st.session_state.chat_history)

            # ----- Token extraction -----
            nav_tab = None
            date_update = None
            source_update = None
            alert_update = None
            country_update = None
            chart_specs = []

            # NAVIGATE
            for m in re.finditer(r"\[\[NAVIGATE:\s*(.*?)\]\]", response):
                nav_tab = m.group(1).strip()
                response = response.replace(m.group(0), "").strip()

            # SET_DATE
            for m in re.finditer(r"\[\[SET_DATE:\s*(.*?),\s*(.*?)\]\]", response):
                try:
                    from datetime import datetime as dt
                    date_update = (
                        dt.strptime(m.group(1).strip(), "%Y-%m-%d").date(),
                        dt.strptime(m.group(2).strip(), "%Y-%m-%d").date(),
                    )
                    response = response.replace(m.group(0), "").strip()
                except Exception as e:
                    logger.error(f"Date parse error: {e}")

            # SET_SOURCE
            for m in re.finditer(r"\[\[SET_SOURCE:\s*(.*?)\]\]", response):
                source_update = m.group(1).strip()
                response = response.replace(m.group(0), "").strip()

            # SET_ALERT
            for m in re.finditer(r"\[\[SET_ALERT:\s*(.*?)\]\]", response):
                alert_update = [x.strip() for x in m.group(1).split(",")]
                response = response.replace(m.group(0), "").strip()

            # SET_COUNTRY
            for m in re.finditer(r"\[\[SET_COUNTRY:\s*(.*?)\]\]", response):
                country_update = [x.strip() for x in m.group(1).split(",")]
                response = response.replace(m.group(0), "").strip()

            # CHART (can be multiple)
            for m in re.finditer(r"\[\[CHART:\s*(.*?)\]\]", response, re.DOTALL):
                spec = {}
                for item in m.group(1).split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        spec[k.strip()] = v.strip()
                chart_specs.append(spec)
                response = response.replace(m.group(0), "").strip()

            # ----- Render response text -----
            st.markdown(response.strip())

            # ----- Render charts (each with its own filter) -----
            for spec in chart_specs:
                # Charts use the FULL df so they can filter independently
                fig = build_ai_chart(spec, filtered_df)
                if fig:
                    st.session_state.ai_chart_counter += 1
                    chart_key = f"ai_chart_{key_suffix}_{st.session_state.ai_chart_counter}"
                    render_plotly_chart(fig, key=chart_key)
                else:
                    c_title = spec.get("title", "chart")
                    f_alert = spec.get("filter_alert", "")
                    st.info(f"ℹ️ No data available for \"{c_title}\" — the filter (alert={f_alert}) returned no results.")

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response.strip(),
                "chart_specs": chart_specs,  # Persist charts for tab-switch survival
            })

            # ----- Apply dashboard-level changes -----
            should_rerun = False
            if nav_tab and nav_tab in ["Overview", "Distribution", "Geographic", "Time Series", "AI Assistant"]:
                st.session_state.active_tab = nav_tab
                should_rerun = True
            if date_update:
                st.session_state.pending_date_update = date_update
                should_rerun = True

            if any([source_update, alert_update, country_update]):
                pending = st.session_state.get("pending_filter_updates", {})
                if source_update:
                    valid_sources = ["USGS", "GDACS", "Both"]
                    normalized = next((s for s in valid_sources if s.lower() == source_update.lower()), None)
                    if normalized:
                        pending["source_select"] = normalized
                if alert_update:
                    avail = filtered_df["alert_level"].dropna().unique().tolist()
                    validated = [a for req in alert_update for a in avail if a.lower() == req.lower()]
                    if validated:
                        pending["alert_multiselect"] = validated
                if country_update:
                    avail_c = filtered_df["country"].dropna().unique().tolist()
                    validated_c = [c for req in country_update for c in avail_c if c.lower() == req.lower()]
                    if validated_c:
                        pending["country_multiselect"] = validated_c
                if pending:
                    st.session_state.pending_filter_updates = pending
                    should_rerun = True

            if should_rerun:
                st.rerun()

# ---------- Floating AI Assistant ----------
# Apply floating CSS to position the popover button in the bottom-right corner of the viewport
st.markdown("""
    <style>
    /* target the popover container and force it to be a small square in the bottom right */
    [data-testid="stPopover"] {
        position: fixed !important;
        bottom: 30px !important;
        right: 30px !important;
        width: auto !important;
        height: auto !important;
        z-index: 999999 !important;
    }
    
    /* Ensure the wrapper doesn't have a background or border that stretches */
    [data-testid="stPopover"] > div:first-child {
        background: transparent !important;
        border: none !important;
    }

    /* target the popover button */
    [data-testid="stPopover"] > button {
        border-radius: 50% !important;
        width: 65px !important;
        height: 65px !important;
        background-color: #3b82f6 !important;
        color: white !important;
        font-size: 28px !important;
        box-shadow: 0 8px 25px rgba(0,0,0,0.4) !important;
        border: 2px solid white !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.3s ease-in-out !important;
    }
    
    [data-testid="stPopover"] > button:hover {
        background-color: #2563eb !important;
        transform: scale(1.15) rotate(5deg) !important;
    }

    /* Style the popover content window */
    [data-testid="stPopoverContent"] {
        width: 400px !important;
        max-height: 600px !important;
        border-radius: 15px !important;
        bottom: 100px !important; /* Push it up above the button */
        right: 0px !important;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3) !important;
    }
    </style>
""", unsafe_allow_html=True)

if st.session_state.active_tab != "AI Assistant":
    with st.popover("🤖"):
        render_ai_chat(filtered, key_suffix="popover")

# ---------- Tabbed dashboard layout ----------
tabs = ["Overview", "Distribution", "Geographic", "Time Series", "AI Assistant"]

def on_tab_change():
    # Sync the selection to our active_tab state
    st.session_state.active_tab = st.session_state.nav_radio

st.radio(
    "Navigation", 
    options=tabs, 
    key="nav_radio",
    index=tabs.index(st.session_state.active_tab),
    on_change=on_tab_change,
    horizontal=True, 
    label_visibility="collapsed"
)

# Render content based on active_tab
if st.session_state.active_tab == "Overview":
    st.subheader("Top countries / regions (by earthquake count)")
    country_counts = filtered["country"].value_counts().sort_values(ascending=False).head(20)
    fig_country = px.bar(
        country_counts,
        labels={"value": "Earthquake Count", "index": "Country"},
        title="Top 20 Affected Countries/Regions",
    )
    render_plotly_chart(fig_country)

    st.subheader("Recent Significant Earthquakes")
    top_n = st.slider("Rows to show", min_value=5, max_value=10, value=10, step=1, key="significant_top_n")

    render_significant_quakes_table(filtered, top_n)

elif st.session_state.active_tab == "Distribution":
    col5, col6 = st.columns(2)
    # ... rest of distribution content ...

    with col5:
        st.subheader("Alert level distribution (pie)")
        alert_counts = filtered["alert_level"].value_counts().sort_values(ascending=False)
        fig_pie = px.pie(
            names=alert_counts.index,
            values=alert_counts.values,
            color=alert_counts.index,
            color_discrete_map=ALERT_HEX_COLORS,
            hole=0.4,
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        render_plotly_chart(fig_pie)

    with col6:
        st.subheader("Magnitude distribution (histogram)")
        mags = pd.to_numeric(filtered["magnitude"], errors="coerce").dropna()
        fig_hist = px.histogram(
            mags,
            nbins=20,
            labels={"value": "Magnitude"},
            title="Frequency of Earthquakes by Magnitude",
        )
        render_plotly_chart(fig_hist)

    col7, col8 = st.columns(2)
    with col7:
        st.subheader("Magnitude by country (boxplot)")
        box_df = filtered[["country", "magnitude"]].copy()
        box_df["magnitude"] = pd.to_numeric(box_df["magnitude"], errors="coerce")
        box_df = box_df.dropna(subset=["country", "magnitude"])
        if not box_df.empty:
            top_countries = box_df["country"].value_counts().head(10).index.tolist()
            box_df = box_df[box_df["country"].isin(top_countries)]
            fig_box = px.box(
                box_df,
                x="country",
                y="magnitude",
                color="country",
                points="outliers",
                title="Magnitude Range in Top 10 Countries",
                labels={"magnitude": "Magnitude", "country": "Country"},
            )
            render_plotly_chart(fig_box)
        else:
            st.info("Not enough data for boxplot.")

    with col8:
        st.subheader("Alert levels by country (stacked bar)")
        if not filtered.empty:
            alert_by_country = filtered.groupby(["country", "alert_level"]).size().reset_index(name="count")
            top_countries = alert_by_country.groupby("country")["count"].sum().sort_values(ascending=False).head(10).index
            alert_by_country = alert_by_country[alert_by_country["country"].isin(top_countries)]
            
            fig_stacked = px.bar(
                alert_by_country,
                x="country",
                y="count",
                color="alert_level",
                color_discrete_map=ALERT_HEX_COLORS,
                title="Alert Levels across Top 10 Countries",
                labels={"count": "Earthquake Count", "country": "Country", "alert_level": "Alert Level"},
            )
            render_plotly_chart(fig_stacked)
        else:
            st.info("No data for stacked bar chart.")

    st.subheader("Top 10 Most-Felt Earthquakes")
    felt_df = filtered[["place", "magnitude", "felt"]].copy()
    felt_df["felt"] = pd.to_numeric(felt_df["felt"], errors="coerce")
    felt_df["magnitude"] = pd.to_numeric(felt_df["magnitude"], errors="coerce")
    felt_df = felt_df.dropna(subset=["felt"])
    felt_df = felt_df[felt_df["felt"] > 0]

    if felt_df.empty:
        st.info("No felt-report data available for the current filters.")
    else:
        felt_top = felt_df.sort_values("felt", ascending=False).head(10)
        fig_felt = px.bar(
            felt_top,
            x="felt",
            y="place",
            orientation="h",
            color="magnitude",
            labels={"felt": "Report Count", "place": "Location", "magnitude": "Magnitude"},
            title="Top 10 Most-Felt Earthquakes",
            hover_data=["magnitude", "felt"],
        )
        fig_felt.update_layout(yaxis={'categoryorder':'total ascending'})
        render_plotly_chart(fig_felt)

elif st.session_state.active_tab == "Geographic":
    st.subheader("Earthquake Map (hover for details)")
    render_earthquake_map(filtered, max_points=max_points)

    st.subheader("Depth vs Magnitude (scatter)")
    scatter_df = filtered[["depth_km", "magnitude", "place", "alert_level"]].dropna(subset=["depth_km", "magnitude"])
    if not scatter_df.empty:
        fig_scatter = px.scatter(
            scatter_df,
            x="depth_km",
            y="magnitude",
            color="alert_level",
            color_discrete_map=ALERT_HEX_COLORS,
            hover_data=["place", "magnitude", "depth_km"],
            labels={"depth_km": "Depth (km)", "magnitude": "Magnitude", "alert_level": "Alert Level"},
            title="Magnitude vs Depth Distribution",
        )
        render_plotly_chart(fig_scatter)
    else:
        st.info("Not enough data for scatter plot.")

elif st.session_state.active_tab == "Time Series":
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Daily earthquake count")
        fig_daily = px.line(
            daily_count.reset_index(),
            x="date_utc",
            y=0,
            labels={"date_utc": "Date (UTC)", "0": "Count"},
            title="Frequency over Time",
        )
        render_plotly_chart(fig_daily)
    with col2:
        st.subheader("Daily average magnitude")
        fig_avg_mag = px.line(
            daily_avg_mag.reset_index(),
            x="date_utc",
            y="magnitude",
            labels={"date_utc": "Date (UTC)", "magnitude": "Avg Magnitude"},
            title="Energy Trend over Time",
        )
        render_plotly_chart(fig_avg_mag)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Cumulative earthquakes")
        fig_cumul = px.area(
            cumulative_quakes.reset_index(),
            x="date_utc",
            y=0,
            labels={"date_utc": "Date (UTC)", "0": "Total Quakes"},
            title="Cumulative Growth",
        )
        render_plotly_chart(fig_cumul)
    with col4:
        st.subheader("Alert level distribution")
        level_counts = filtered["alert_level"].value_counts().sort_values(ascending=False)
        fig_lvl_bar = px.bar(
            level_counts,
            labels={"index": "Alert Level", "value": "Count"},
            color=level_counts.index,
            color_discrete_map=ALERT_HEX_COLORS,
            title="Totals by Alert Level",
        )
        render_plotly_chart(fig_lvl_bar)

    st.subheader("Daily earthquakes (7-day rolling average)")
    rolling = daily_count.rolling(7).mean()
    
    fig_smooth = go.Figure()
    fig_smooth.add_trace(go.Scatter(
        x=daily_count.index, y=daily_count.values,
        mode='lines', name='Daily Count',
        line=dict(color='#3b82f6', width=1),
        opacity=0.4
    ))
    fig_smooth.add_trace(go.Scatter(
        x=rolling.index, y=rolling.values,
        mode='lines', name='7-day rolling avg',
        line=dict(color='#60a5fa', width=3)
    ))
    fig_smooth.update_layout(
        title="Smoothed Earthquake Trends",
        xaxis_title="Date (UTC)",
        yaxis_title="Count",
    )
    render_plotly_chart(fig_smooth)

elif st.session_state.active_tab == "AI Assistant":
    render_ai_chat(filtered, key_suffix="tab")
