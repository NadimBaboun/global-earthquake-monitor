import os
import time
import pandas as pd
import streamlit as st

from datetime import datetime, timezone, timedelta
from data import CONFIG, load_data_by_source
from config import UI_CONFIG
from chart_utils import render_plotly_chart
import plotly.express as px
import plotly.graph_objects as go
from constants import ALERT_HEX_COLORS
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

with tab_distribution:
    col5, col6 = st.columns(2)

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

with tab_geographic:
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

with tab_timeseries:
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

# Timed auto-refresh (10 min) for live dashboard mode
if auto_refresh:
    time.sleep(600)
    st.rerun()