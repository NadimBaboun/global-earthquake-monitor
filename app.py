import pandas as pd
import streamlit as st

from datetime import datetime, timezone, timedelta
from data import CONFIG, load_data_with_cache
from chart_utils import dark_chart, DARK_FG

st.set_page_config(page_title="Global Disaster Monitor (GDACS)", page_icon="🌐", layout="wide")

# ---------- UI ----------
st.title("Global Disaster Monitor — Live Alerts Dashboard")
st.caption("Source: GDACS RSS feed (near real-time natural disaster alerts)")

df, warn = load_data_with_cache()
if warn:
    st.warning(warn)

if df is None or df.empty:
    st.error("No data available.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters (UTC)")

all_types = sorted([x for x in df["event_type"].dropna().unique().tolist() if x])
all_levels = sorted([x for x in df["alert_level"].dropna().unique().tolist() if x])
all_countries = sorted([x for x in df["country"].dropna().unique().tolist() if x])

selected_types = st.sidebar.multiselect("Event type", all_types)
selected_levels = st.sidebar.multiselect("Alert level", all_levels)
selected_countries = st.sidebar.multiselect("Country", all_countries)

today_utc = datetime.now(timezone.utc).date()
default_start = today_utc - timedelta(days=CONFIG["default_days_back"])
date_range = st.sidebar.date_input("Date range", value=(default_start, today_utc))

max_points = st.sidebar.slider("Map points (highest alert score)", CONFIG["map_points_min"], CONFIG["map_points_max"], CONFIG["map_points_default"], CONFIG["map_points_min"])

# date_input returns a single date while the user is mid-selection; guard against that
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = default_start, today_utc

# Require at least one selection per filter to avoid rendering charts on the full unfiltered dataset
no_filter_selected = (not selected_types) or (not selected_levels) or (not selected_countries)
if no_filter_selected:
    st.info("Please select at least one option from each filter to continue.")
    st.stop()

# Apply all sidebar selections as a single boolean mask for efficiency
mask = (
    df["event_type"].isin(selected_types)
    & df["alert_level"].isin(selected_levels)
    & df["country"].isin(selected_countries)
    & df["date_utc"].between(start_d, end_d)
)
filtered = df.loc[mask].copy()

if filtered.empty:
    st.warning("No records match your filters.")
    st.stop()

# Quick-glance metrics so users can assess severity without scrolling
st.sidebar.subheader("Summary")
st.sidebar.write("Alerts:", int(len(filtered)))

avg_score = pd.to_numeric(filtered["alert_score"], errors="coerce").mean()
max_score = pd.to_numeric(filtered["alert_score"], errors="coerce").max()
st.sidebar.write("Avg alert score:", float(avg_score) if pd.notna(avg_score) else "N/A")
st.sidebar.write("Max alert score:", float(max_score) if pd.notna(max_score) else "N/A")

# Pre-compute daily aggregates once; reused by multiple charts below
daily_count = filtered.groupby("date_utc").size()
daily_avg_score = filtered.groupby("date_utc")["alert_score"].mean()
cumulative_alerts = daily_count.cumsum()

# Collapsible table lets users inspect exact numbers behind the trend charts
st.sidebar.subheader("Daily summary")
show_all_days = st.sidebar.checkbox("Show all days", value=True)

summary_tbl = pd.DataFrame(
    {
        "date_utc": daily_count.index,
        "alerts": daily_count.values,
        "avg_alert_score": daily_avg_score.reindex(daily_count.index).values,
    }
).reset_index(drop=True)

if not show_all_days:
    summary_tbl = summary_tbl.tail(10)

summary_tbl.index = range(1, len(summary_tbl) + 1)

st.sidebar.dataframe(
    summary_tbl,
    use_container_width=True,
    height=CONFIG["sidebar_table_height"],
)

# ---------- Main charts (Streamlit built-ins) ----------
col1, col2 = st.columns(2)
with col1:
    st.subheader("Daily alert count")
    st.line_chart(daily_count)

with col2:
    st.subheader("Daily average alert score")
    st.line_chart(daily_avg_score)

col3, col4 = st.columns(2)
with col3:
    st.subheader("Cumulative alerts")
    st.line_chart(cumulative_alerts)

with col4:
    st.subheader("Alert level distribution")
    level_counts = filtered["alert_level"].value_counts().sort_values(ascending=False)
    st.bar_chart(level_counts, height=CONFIG["chart_height_small"])

st.subheader("Top countries (by alert count)")
country_counts = filtered["country"].value_counts().sort_values(ascending=False)
st.bar_chart(country_counts, height=CONFIG["chart_height_medium"])

# ---------- Matplotlib charts (ALL dark themed) ----------
# Row 1: Pie (event types) + Histogram (alert scores)
col5, col6 = st.columns(2)

with col5:
    st.subheader("Event type distribution (pie)")
    event_counts = filtered["event_type"].value_counts().sort_values(ascending=False)

    with dark_chart(title="Event type distribution", figsize=CONFIG["figsize_square"], tight=False) as (fig, ax):
        ax.pie(
            event_counts.values,
            labels=event_counts.index,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"color": DARK_FG},
        )
        ax.axis("equal")

with col6:
    st.subheader("Alert score distribution (histogram)")
    scores = pd.to_numeric(filtered["alert_score"], errors="coerce").dropna()

    with dark_chart("Distribution of alert scores", "Alert score", "Frequency", figsize=(8, 4)) as (fig, ax):
        ax.hist(scores, bins=CONFIG["map_points_min"])

col7, col8 = st.columns(2)

with col7:
    st.subheader("Alert score by event type (boxplot)")
    box_df = filtered[["event_type", "alert_score"]].copy()
    box_df["alert_score"] = pd.to_numeric(box_df["alert_score"], errors="coerce")
    box_df = box_df.dropna(subset=["event_type", "alert_score"])

    if not box_df.empty:
        # Sort event types by median score so the most severe appear first
        order = (
            box_df.groupby("event_type")["alert_score"]
            .median()
            .sort_values(ascending=False)
            .index.tolist()
        )
        data = [box_df.loc[box_df["event_type"] == t, "alert_score"].values for t in order]

        with dark_chart("Alert score by event type", "Event type", "Alert score", rotate_x=True) as (fig, ax):
            ax.boxplot(data, labels=order, showfliers=False)
    else:
        st.info("Not enough numeric alert_score values to draw the boxplot.")

with col8:
    st.subheader("Alert levels by event type (stacked bar)")
    stacked = (
        filtered.groupby(["event_type", "alert_level"])
        .size()
        .unstack(fill_value=0)
    )

    if not stacked.empty:
        with dark_chart("Alert levels by event type", "Event type", "Count", rotate_x=True, legend="Alert level") as (fig, ax):
            stacked.plot(kind="bar", stacked=True, ax=ax)
    else:
        st.info("No data available for stacked bar chart.")

# Row 3: Trend by type + Rolling average
col9, col10 = st.columns(2)

with col9:
    st.subheader("Alerts over time by event type (trend)")
    pivot = (
        filtered.groupby(["date_utc", "event_type"])
        .size()
        .unstack(fill_value=0)
    )

    if not pivot.empty:
        with dark_chart("Alerts over time by event type", "Date (UTC)", "Alerts", rotate_x=True, legend="Event type") as (fig, ax):
            pivot.plot(ax=ax)
    else:
        st.info("Not enough data to plot event-type trends over time.")

with col10:
    st.subheader("Daily alerts (7-day rolling average)")
    rolling = daily_count.rolling(7).mean()

    with dark_chart("Daily alerts (smoothed)", "Date (UTC)", "Alerts", figsize=CONFIG["figsize_wide"], rotate_x=True, legend="") as (fig, ax):
        ax.plot(daily_count.index, daily_count.values, label="Daily", alpha=0.4)
        ax.plot(rolling.index, rolling.values, label="7-day rolling avg")

# ---------- Map ----------
# Show only the top-N most severe events to keep the map readable
st.subheader("Map (highest alert score)")
map_df = (
    filtered.dropna(subset=["latitude", "longitude", "alert_score"])
    .sort_values("alert_score", ascending=False)
    .head(max_points)
)
st.map(map_df[["latitude", "longitude"]])