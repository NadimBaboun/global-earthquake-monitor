import os
import time
import pandas as pd
import streamlit as st

from datetime import datetime, timezone, timedelta
from data import CONFIG, load_data_by_source
from config import UI_CONFIG
from chart_utils import dark_chart, DARK_FG
from constants import ALERT_HEX_COLORS, DEFAULT_ALERT_HEX
from map_utils import render_earthquake_map
from components import inject_custom_css, render_significant_quakes_table

st.set_page_config(page_title="Global Earthquake Monitor (USGS)", page_icon="🌍", layout="wide")

# Inject custom styling for metrics and tables
inject_custom_css()

# ---------- UI ----------
st.title("Global Earthquake Monitor — Live Dashboard")

# Sidebar: date range picker (drives the API query)
st.sidebar.header("Data Source (UTC)")
source_label = st.sidebar.radio("Source", ["USGS", "GDACS", "Both"], index=0, horizontal=True)

today_utc = datetime.now(timezone.utc).date()
default_start = today_utc - timedelta(days=UI_CONFIG["default_days_back"])
date_range = st.sidebar.date_input("Date range", value=(default_start, today_utc))

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
auto_refresh = st.sidebar.checkbox("Auto-refresh every 10 min", value=False)

# Fetch data using the selected date range and magnitude
from_str = start_d.strftime("%Y-%m-%d")
to_str = end_d.strftime("%Y-%m-%d")

with st.spinner("Fetching earthquake data..."):
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

selected_levels = st.sidebar.multiselect("Alert level", all_levels, default=all_levels)
selected_countries = st.sidebar.multiselect("Country / Region", all_countries, default=all_countries)
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

# Pre-compute daily aggregates
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

# ---------- Tabbed dashboard layout ----------
tab_overview, tab_distribution, tab_geographic, tab_timeseries = st.tabs(
    ["Overview", "Distribution", "Geographic", "Time Series"]
)

with tab_overview:
    st.subheader("Top countries / regions (by earthquake count)")
    country_counts = filtered["country"].value_counts().sort_values(ascending=False)
    st.bar_chart(country_counts, height=UI_CONFIG["chart_height_medium"])

    st.subheader("Recent Significant Earthquakes")
    top_n = st.slider("Rows to show", min_value=5, max_value=10, value=10, step=1, key="significant_top_n")

    render_significant_quakes_table(filtered, top_n)

with tab_distribution:
    col5, col6 = st.columns(2)

    with col5:
        st.subheader("Alert level distribution (pie)")
        alert_counts = filtered["alert_level"].value_counts().sort_values(ascending=False)

        with dark_chart(title="Alert level distribution", figsize=UI_CONFIG["figsize_square"], tight=False) as (fig, ax):
            pie_colors = [ALERT_HEX_COLORS.get(level, DEFAULT_ALERT_HEX) for level in alert_counts.index]
            ax.pie(
                alert_counts.values,
                labels=alert_counts.index,
                autopct="%1.1f%%",
                startangle=90,
                colors=pie_colors,
                textprops={"color": DARK_FG},
            )
            ax.axis("equal")

    with col6:
        st.subheader("Magnitude distribution (histogram)")
        mags = pd.to_numeric(filtered["magnitude"], errors="coerce").dropna()
        with dark_chart("Distribution of magnitudes", "Magnitude", "Frequency", figsize=(8, 4)) as (fig, ax):
            ax.hist(mags, bins=UI_CONFIG["histogram_bins"], color="#3b82f6", edgecolor="#1e40af")

    col7, col8 = st.columns(2)
    with col7:
        st.subheader("Magnitude by country (boxplot)")
        box_df = filtered[["country", "magnitude"]].copy()
        box_df["magnitude"] = pd.to_numeric(box_df["magnitude"], errors="coerce")
        box_df = box_df.dropna(subset=["country", "magnitude"])
        if not box_df.empty:
            top_countries = box_df["country"].value_counts().head(10).index.tolist()
            box_df = box_df[box_df["country"].isin(top_countries)]
            order = (
                box_df.groupby("country")["magnitude"]
                .median()
                .sort_values(ascending=False)
                .index.tolist()
            )
            data = [box_df.loc[box_df["country"] == c, "magnitude"].values for c in order]
            with dark_chart("Magnitude by country (top 10)", "Country", "Magnitude", rotate_x=True) as (fig, ax):
                ax.boxplot(data, tick_labels=order, showfliers=False)
        else:
            st.info("Not enough data for boxplot.")

    with col8:
        st.subheader("Alert levels by country (stacked bar)")
        stacked = (
            filtered.groupby(["country", "alert_level"])
            .size()
            .unstack(fill_value=0)
        )
        if not stacked.empty:
            top = stacked.sum(axis=1).sort_values(ascending=False).head(10).index
            stacked = stacked.loc[top]
            with dark_chart("Alert levels by country", "Country", "Count", rotate_x=True, legend="Alert level") as (fig, ax):
                stacked.plot(kind="bar", stacked=True, ax=ax,
                             color=[ALERT_HEX_COLORS.get(c, DEFAULT_ALERT_HEX) for c in stacked.columns])
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
        felt_top = felt_df.sort_values("felt", ascending=False).head(10).copy()
        felt_top["label"] = felt_top.apply(
            lambda r: f"{r['place']} (M{r['magnitude']:.1f})" if pd.notna(r["magnitude"]) else f"{r['place']} (M N/A)",
            axis=1,
        )
        felt_top = felt_top.iloc[::-1]
        felt_series = pd.Series(felt_top["felt"].values, index=felt_top["label"].values)
        st.bar_chart(felt_series, horizontal=True, height=UI_CONFIG["chart_height_medium"])

with tab_geographic:
    st.subheader("Earthquake Map (hover for details)")
    render_earthquake_map(filtered, max_points=max_points)

    st.subheader("Depth vs Magnitude (scatter)")
    scatter_df = filtered[["depth_km", "magnitude"]].dropna()
    if not scatter_df.empty:
        with dark_chart("Depth vs Magnitude", "Depth (km)", "Magnitude") as (fig, ax):
            ax.scatter(scatter_df["depth_km"], scatter_df["magnitude"], alpha=0.5, s=15, c="#3b82f6")
    else:
        st.info("Not enough data for scatter plot.")

with tab_timeseries:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Daily earthquake count")
        st.line_chart(daily_count)
    with col2:
        st.subheader("Daily average magnitude")
        st.line_chart(daily_avg_mag)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Cumulative earthquakes")
        st.line_chart(cumulative_quakes)
    with col4:
        st.subheader("Alert level distribution")
        level_counts = filtered["alert_level"].value_counts().sort_values(ascending=False)
        st.bar_chart(level_counts, height=UI_CONFIG["chart_height_small"])

    st.subheader("Daily earthquakes (7-day rolling average)")
    rolling = daily_count.rolling(7).mean()
    with dark_chart("Daily earthquakes (smoothed)", "Date (UTC)", "Count", figsize=UI_CONFIG["figsize_wide"], rotate_x=True, legend="") as (fig, ax):
        ax.plot(daily_count.index, daily_count.values, label="Daily", alpha=0.4)
        ax.plot(rolling.index, rolling.values, label="7-day rolling avg")

# Timed auto-refresh (10 min) for live dashboard mode
if auto_refresh:
    time.sleep(600)
    st.rerun()