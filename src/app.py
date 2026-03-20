import os
import pandas as pd
import streamlit as st
import logging
from datetime import datetime, timezone, timedelta
from data import CONFIG, load_data_by_source
from config import UI_CONFIG
from ai.ai_utils import SeismicAI
from ui.components import inject_custom_css, inject_floating_ai_css
from ai.ai_components import render_ai_chat
from ui.tabs import (
    render_overview_tab,
    render_distribution_tab,
    render_geographic_tab,
    render_timeseries_tab,
)
from utils.data_utils import compute_daily_aggregates

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Global Earthquake Monitor (USGS)", page_icon="🌍", layout="wide"
)

# Inject custom styling for metrics and tables
inject_custom_css()
inject_floating_ai_css()

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

if "pending_nav_update" in st.session_state:
    update = st.session_state.pop("pending_nav_update")
    st.session_state.active_tab = update
    st.session_state.nav_radio = update

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

if "nav_radio" not in st.session_state:
    st.session_state.nav_radio = st.session_state.active_tab

if "source_select" not in st.session_state:
    st.session_state.source_select = "USGS"

# ---------- UI ----------
st.title("Global Earthquake Monitor — Live Dashboard")

# Sidebar: date range picker (drives the API query)
st.sidebar.header("Data Source (UTC)")
source_label = st.sidebar.radio(
    "Source", ["USGS", "GDACS", "Both"], horizontal=True, key="source_select"
)

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
    min_value=1.0,
    max_value=8.0,
    value=CONFIG["default_min_magnitude"],
    step=0.5,
)
# Auto-refresh checkbox removed due to navigation performance issues.

# Fetch data using the selected date range and magnitude
start_str = start_d.strftime("%Y-%m-%d")
end_str = end_d.strftime("%Y-%m-%d")

df, warn = load_data_by_source(
    start_date=start_str,
    end_date=end_str,
    min_mag=min_mag,
    source=source_label,
)
if warn:
    st.warning(warn)

if df is None or df.empty:
    st.error("No earthquake data available for the selected criteria.")
    st.stop()

xml_path = CONFIG["xml_output_file"]

# Sidebar filters
st.sidebar.header("Filters")

all_levels = sorted([x for x in df["alert_level"].dropna().unique().tolist() if x])
all_countries = sorted([x for x in df["country"].dropna().unique().tolist() if x])

# Initialize filter states if missing (cannot do this before data is loaded)
if "alert_multiselect" not in st.session_state:
    st.session_state.alert_multiselect = all_levels
if "country_multiselect" not in st.session_state:
    st.session_state.country_multiselect = all_countries

selected_levels = st.sidebar.multiselect(
    "Alert level", all_levels, key="alert_multiselect"
)
selected_countries = st.sidebar.multiselect(
    "Country / Region", all_countries, key="country_multiselect"
)
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
    filtered["tsunami"] = (
        pd.to_numeric(filtered["tsunami"], errors="coerce").fillna(0).astype(int)
    )
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
tsunami_count = (
    int((filtered["tsunami"] == 1).sum()) if "tsunami" in filtered.columns else 0
)
st.sidebar.metric("Tsunami Advisories", tsunami_count)

# Bottom of sidebar: Last updated and Download
last_updated_utc = datetime.now(timezone.utc)
st.sidebar.divider()
st.sidebar.caption(f"Last updated: {last_updated_utc.strftime('%Y-%m-%d %H:%M UTC')}")

if source_label in {"USGS", "Both"} and os.path.exists(xml_path):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml_content = f.read()
    st.sidebar.download_button(
        label="📥 Download XML (QuakeML)",
        data=xml_content,
        file_name="earthquakes.xml",
        mime="application/xml",
    )

# Pre-compute daily aggregates for graphs
daily_count, daily_avg_mag, daily_energy, cumulative_energy = compute_daily_aggregates(
    filtered
)

# ---------- Floating AI Assistant ----------
# ---------- Tabs & Routing ----------
if st.session_state.active_tab != "AI Assistant":
    with st.popover("🤖"):
        render_ai_chat(filtered, ai, key_suffix="popover")

# ---------- Tabbed dashboard layout ----------
tabs = ["Overview", "Distribution", "Geographic", "Time Series", "AI Assistant"]


def on_tab_change() -> None:
    """Sync the navigation radio selection to the active_tab session state."""
    st.session_state.active_tab = st.session_state.nav_radio


st.radio(
    "Navigation",
    options=tabs,
    key="nav_radio",
    on_change=on_tab_change,
    horizontal=True,
    label_visibility="collapsed",
)

# Render content based on active_tab
if st.session_state.active_tab == "Overview":
    render_overview_tab(filtered)
elif st.session_state.active_tab == "Distribution":
    render_distribution_tab(filtered)
elif st.session_state.active_tab == "Geographic":
    render_geographic_tab(filtered)
elif st.session_state.active_tab == "Time Series":
    render_timeseries_tab(filtered, daily_count, daily_avg_mag, cumulative_energy)
elif st.session_state.active_tab == "AI Assistant":
    render_ai_chat(filtered, ai, key_suffix="tab")
