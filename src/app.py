import os

import pandas as pd
import streamlit as st

from datetime import datetime, timezone, timedelta
from data import CONFIG, load_data_with_cache
from chart_utils import dark_chart, DARK_FG
from map_utils import render_earthquake_map

st.set_page_config(page_title="Global Earthquake Monitor (USGS)", page_icon="🌍", layout="wide")

# ---------- UI ----------
st.title("Global Earthquake Monitor — Live Dashboard")
st.caption("Source: USGS Earthquake Catalog API · Historical data with date range selection · XML export for XSLT")

# Sidebar: date range picker (drives the API query)
st.sidebar.header("Data Source (UTC)")

today_utc = datetime.now(timezone.utc).date()
default_start = today_utc - timedelta(days=CONFIG["default_days_back"])
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

# Fetch data using the selected date range and magnitude
from_str = start_d.strftime("%Y-%m-%d")
to_str = end_d.strftime("%Y-%m-%d")

df, warn = load_data_with_cache(from_date=from_str, to_date=to_str, min_magnitude=min_mag)
if warn:
    st.warning(warn)

if df is None or df.empty:
    st.error("No earthquake data available for the selected criteria.")
    st.stop()

# XML download button
xml_path = CONFIG["xml_output_file"]
if os.path.exists(xml_path):
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
selected_countries = st.sidebar.multiselect("Country / Region", all_countries)

max_points = st.sidebar.slider("Map points", CONFIG["map_points_min"], CONFIG["map_points_max"], CONFIG["map_points_default"], CONFIG["map_points_min"])

# Require at least one country selection
if not selected_countries:
    st.info("Please select at least one country/region to continue.")
    st.stop()

# Apply filters
mask = (
    df["alert_level"].isin(selected_levels)
    & df["country"].isin(selected_countries)
    & df["date_utc"].between(start_d, end_d)
)
filtered = df.loc[mask].copy()

if filtered.empty:
    st.warning("No records match your filters.")
    st.stop()

# Quick-glance metrics
st.sidebar.subheader("Summary")
st.sidebar.write("Earthquakes:", int(len(filtered)))

avg_mag = pd.to_numeric(filtered["magnitude"], errors="coerce").mean()
max_mag = pd.to_numeric(filtered["magnitude"], errors="coerce").max()
st.sidebar.write("Avg magnitude:", round(float(avg_mag), 1) if pd.notna(avg_mag) else "N/A")
st.sidebar.write("Max magnitude:", round(float(max_mag), 1) if pd.notna(max_mag) else "N/A")

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
    height=CONFIG["sidebar_table_height"],
)

# ---------- Main charts (Streamlit built-ins) ----------
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
    st.bar_chart(level_counts, height=CONFIG["chart_height_small"])

st.subheader("Top countries / regions (by earthquake count)")
country_counts = filtered["country"].value_counts().sort_values(ascending=False)
st.bar_chart(country_counts, height=CONFIG["chart_height_medium"])

# ---------- Matplotlib charts (dark themed) ----------
col5, col6 = st.columns(2)

with col5:
    st.subheader("Alert level distribution (pie)")
    alert_counts = filtered["alert_level"].value_counts().sort_values(ascending=False)

    with dark_chart(title="Alert level distribution", figsize=CONFIG["figsize_square"], tight=False) as (fig, ax):
        colors = {"Red": "#ef4444", "Orange": "#f97316", "Green": "#22c55e", "Unknown": "#6b7280"}
        pie_colors = [colors.get(l, "#6b7280") for l in alert_counts.index]
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
        ax.hist(mags, bins=CONFIG["map_points_min"], color="#3b82f6", edgecolor="#1e40af")

col7, col8 = st.columns(2)

with col7:
    st.subheader("Magnitude by country (boxplot)")
    box_df = filtered[["country", "magnitude"]].copy()
    box_df["magnitude"] = pd.to_numeric(box_df["magnitude"], errors="coerce")
    box_df = box_df.dropna(subset=["country", "magnitude"])

    if not box_df.empty:
        # Show top 10 countries by count
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
        # Top 10 countries
        top = stacked.sum(axis=1).sort_values(ascending=False).head(10).index
        stacked = stacked.loc[top]
        with dark_chart("Alert levels by country", "Country", "Count", rotate_x=True, legend="Alert level") as (fig, ax):
            stacked.plot(kind="bar", stacked=True, ax=ax,
                         color=[colors.get(c, "#6b7280") for c in stacked.columns])
    else:
        st.info("No data for stacked bar chart.")

# Row 3: Depth analysis + Rolling average
col9, col10 = st.columns(2)

with col9:
    st.subheader("Depth vs Magnitude (scatter)")
    scatter_df = filtered[["depth_km", "magnitude"]].dropna()
    if not scatter_df.empty:
        with dark_chart("Depth vs Magnitude", "Depth (km)", "Magnitude") as (fig, ax):
            ax.scatter(scatter_df["depth_km"], scatter_df["magnitude"], alpha=0.5, s=15, c="#3b82f6")
    else:
        st.info("Not enough data for scatter plot.")

with col10:
    st.subheader("Daily earthquakes (7-day rolling average)")
    rolling = daily_count.rolling(7).mean()

    with dark_chart("Daily earthquakes (smoothed)", "Date (UTC)", "Count", figsize=CONFIG["figsize_wide"], rotate_x=True, legend="") as (fig, ax):
        ax.plot(daily_count.index, daily_count.values, label="Daily", alpha=0.4)
        ax.plot(rolling.index, rolling.values, label="7-day rolling avg")

# ---------- Interactive Map (pydeck) ----------
st.subheader("Earthquake Map (hover for details)")
render_earthquake_map(filtered, max_points=max_points)