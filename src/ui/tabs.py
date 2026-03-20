"""Dashboard tab components."""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.chart_utils import render_plotly_chart
from constants import ALERT_HEX_COLORS
from utils.map_utils import render_earthquake_map


def render_overview_tab(df: pd.DataFrame) -> None:
    """Renders the Overview tab with key metrics and most recent significant events."""
    st.markdown("""
    Welcome to the **Global Earthquake Monitor**, a professional-grade dashboard for real-time seismic activity tracking and analysis. 
    
    Our platform integrates data from the world's leading seismological organizations to provide you with up-to-the-minute insights into global planetary activity.
    
    ### 🚀 Key Features
    - **Real-Time Tracking**: Live feeds from **USGS** and **GDACS** providers.
    - **Interactive Analytics**: Deep-dive into magnitude distribution and depth profiles.
    - **Geographic Hotspots**: Advanced heatmap and 3D mapping of seismic events.
    - **AI Assistant**: A built-in expert to answer questions and generate custom visualizations.
    - **Trend Analysis**: Comprehensive time-series tracking of seismic energy and frequency.
    
    *Use the navigation above to explore different analytical perspectives or chat with our AI for specific inquiries.*
    """)
    st.divider()
    st.markdown("### 🔔 Highest Magnitude Events")
    from ui.components import render_significant_quakes_table

    render_significant_quakes_table(df, top_n=10)


def render_distribution_tab(df: pd.DataFrame) -> None:
    """Renders distribution histograms and alert level pie charts."""
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Magnitude distribution")
        mags = pd.to_numeric(df["magnitude"], errors="coerce").dropna()
        fig_hist = px.histogram(
            mags,
            nbins=20,
            labels={"value": "Magnitude"},
            title="Frequency by Magnitude",
        )
        render_plotly_chart(fig_hist)
    with col2:
        st.subheader("Alert levels")
        alert_counts = df["alert_level"].value_counts()
        fig_pie = px.pie(
            names=alert_counts.index,
            values=alert_counts.values,
            color=alert_counts.index,
            color_discrete_map=ALERT_HEX_COLORS,
            hole=0.4,
            title="Alert Severity Split",
        )
        render_plotly_chart(fig_pie)

    # New row for more insights
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Top Active Regions")
        region_counts = (
            df["country"].value_counts().head(10).sort_values(ascending=True)
        )
        fig_regions = px.bar(
            x=region_counts.values,
            y=region_counts.index,
            orientation="h",
            labels={"x": "Number of Events", "y": "Region"},
            title="Top 10 Seismically Active Regions",
        )
        render_plotly_chart(fig_regions)
    with col4:
        st.subheader("Magnitude by Alert")
        fig_box = px.box(
            df,
            x="alert_level",
            y="magnitude",
            color="alert_level",
            color_discrete_map=ALERT_HEX_COLORS,
            title="Magnitude Spread per Alert Level",
        )
        render_plotly_chart(fig_box)


def render_geographic_tab(df: pd.DataFrame) -> None:
    """Renders interactive map and depth-magnitude scatter plots."""
    st.subheader("Interactive Map")
    render_earthquake_map(df)
    st.subheader("Magnitude vs Depth")
    scatter_df = df.dropna(subset=["depth_km", "magnitude"])
    fig_scatter = px.scatter(
        scatter_df,
        x="depth_km",
        y="magnitude",
        color="alert_level",
        color_discrete_map=ALERT_HEX_COLORS,
    )
    render_plotly_chart(fig_scatter)


def render_timeseries_tab(
    df: pd.DataFrame,
    daily_count: pd.Series,
    daily_avg_mag: pd.Series,
    cumulative_energy: pd.Series,
) -> None:
    """Renders time-series charts for daily counts and average magnitudes."""
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Daily Count")
        fig_daily = px.line(
            daily_count.reset_index(), x="date_utc", y=0, title="Earthquakes per Day"
        )
        render_plotly_chart(fig_daily)
    with col2:
        st.subheader("Average Magnitude")
        fig_avg = px.line(
            daily_avg_mag.reset_index(),
            x="date_utc",
            y="magnitude",
            title="Daily Avg Intensity",
        )
        render_plotly_chart(fig_avg)

    st.subheader("Cumulative Seismic Energy Release")
    st.markdown(
        "Visualizing the total energy released over time (Relative units using $10^{1.5M}$)"
    )
    fig_energy = px.area(
        cumulative_energy.reset_index(),
        x="date_utc",
        y="energy",
        title="Total Energy Unleashed (Cumulative)",
        line_shape="hv",  # Step chart looks better for cumulative total
    )
    render_plotly_chart(fig_energy)
