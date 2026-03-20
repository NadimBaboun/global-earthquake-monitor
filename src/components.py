"""
UI components and presentation logic for the Global Earthquake Monitor.
"""

import pandas as pd
import streamlit as st
from html import escape

def inject_custom_css():
    """Inject custom CSS for sidebar metrics and other UI elements."""
    st.markdown("""
    <style>
    /* Sidebar metric styling */
    [data-testid="stSidebar"] [data-testid="stMetricValue"] { font-size: 1.1rem; }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] { font-size: 0.75rem; }
    [data-testid="stSidebar"] [data-testid="stMetric"] { padding: 4px 0; }
    
    .sig-table-wrap { overflow-x: auto; margin-bottom: 0.25rem; }
    .sig-table {
        width: 100%;
        border-collapse: collapse;
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 8px;
    }
    .sig-table th, .sig-table td {
        text-align: left;
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        font-size: 0.9rem;
    }
    .sig-table thead th {
        color: #e2e8f0;
        background: rgba(30, 41, 59, 0.6);
        font-weight: 600;
    }
    .sig-table tbody tr:hover {
        background: rgba(59, 130, 246, 0.12);
    }
    .sig-table a {
        color: #60a5fa;
        text-decoration: none;
    }
    .sig-table a:hover {
        text-decoration: underline;
    }
    </style>
    """, unsafe_allow_html=True)

def render_significant_quakes_table(df: pd.DataFrame, top_n: int = 10):
    """
    Process and render a styled HTML table of significant earthquakes.
    
    Parameters
    ----------
    df    : pd.DataFrame Filtered earthquake data.
    top_n : int          Number of rows to display.
    """
    # 1. Prepare data specifically for the table
    sig_df = df[["place", "magnitude", "depth_km", "main_time", "link"]].copy()
    sig_df["magnitude"] = pd.to_numeric(sig_df["magnitude"], errors="coerce")
    sig_df["depth_km"] = pd.to_numeric(sig_df["depth_km"], errors="coerce")
    sig_df = sig_df.dropna(subset=["magnitude"]).sort_values("magnitude", ascending=False).head(top_n)

    if sig_df.empty:
        st.info("No significant earthquakes available for the current filters.")
        return

    # 2. Format columns for display
    sig_df["time_utc"] = pd.to_datetime(sig_df["main_time"], utc=True, errors="coerce").dt.strftime("%Y-%m-%d %H:%M UTC")
    sig_df["magnitude_display"] = sig_df["magnitude"].map(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
    sig_df["depth_display"] = sig_df["depth_km"].map(lambda x: f"{x:.1f} km" if pd.notna(x) else "N/A")

    # 3. Generate HTML rows
    table_rows = []
    for _, row in sig_df.iterrows():
        place = escape(str(row.get("place") or "Unknown location"))
        mag = escape(str(row.get("magnitude_display") or "N/A"))
        depth = escape(str(row.get("depth_display") or "N/A"))
        time_utc = escape(str(row.get("time_utc") or "N/A"))
        link = row.get("link") or ""
        link_html = (
            f'<a href="{escape(str(link), quote=True)}" target="_blank" rel="noopener noreferrer">USGS Event</a>'
            if link
            else "N/A"
        )
        table_rows.append(
            f"<tr><td>{place}</td><td>{mag}</td><td>{depth}</td><td>{time_utc}</td><td>{link_html}</td></tr>"
        )

    # 4. Render the final table
    st.markdown(
        (
            '<div class="sig-table-wrap"><table class="sig-table">'
            "<thead><tr><th>Place</th><th>Magnitude</th><th>Depth</th><th>Time</th><th>Link</th></tr></thead>"
            f"<tbody>{''.join(table_rows)}</tbody>"
            "</table></div>"
        ),
        unsafe_allow_html=True,
    )
