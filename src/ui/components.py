# Standard Library
from html import escape

# Third-Party
import pandas as pd
import streamlit as st


def inject_custom_css() -> None:
    """Inject global CSS for sidebar metrics, title positioning, and tables."""
    st.markdown(
        """
    <style>
    /* Sidebar metric styling */
    [data-testid="stSidebar"] [data-testid="stMetricValue"] { font-size: 1.1rem; }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] { font-size: 0.75rem; }
    [data-testid="stSidebar"] [data-testid="stMetric"] { padding: 4px 0; }
    
    /* Raise main title to align with sidebar */
    .main .block-container {
        padding-top: 0 !important;
        padding-bottom: 2rem !important;
    }
    h1 {
        margin-top: -3.1rem !important;
        margin-bottom: -1rem !important;
        padding-top: 0 !important;
    }
    
    /* Aggressively pull JUST the main area navigation radio up - DEBUG RED */
    .main [data-testid="stRadio"] {
        position: relative !important;
        top: -3.0rem !important;
        background-color: rgba(255, 0, 0, 0.2) !important;
    }
    
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
    """,
        unsafe_allow_html=True,
    )


def inject_floating_ai_css() -> None:
    """Inject CSS for the floating AI assistant popover button and content."""
    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )


def render_significant_quakes_table(df: pd.DataFrame, top_n: int = 10) -> None:
    """Process and render a styled HTML table of the top_n significant earthquakes."""
    sig_df = df[["place", "magnitude", "depth_km", "main_time", "link"]].copy()
    sig_df["magnitude"] = pd.to_numeric(sig_df["magnitude"], errors="coerce")
    sig_df["depth_km"] = pd.to_numeric(sig_df["depth_km"], errors="coerce")
    sig_df = (
        sig_df.dropna(subset=["magnitude"])
        .sort_values("magnitude", ascending=False)
        .head(top_n)
    )

    if sig_df.empty:
        st.info("No significant earthquakes available for the current filters.")
        return

    sig_df["time_utc"] = pd.to_datetime(
        sig_df["main_time"], utc=True, errors="coerce"
    ).dt.strftime("%Y-%m-%d %H:%M UTC")
    sig_df["magnitude_display"] = sig_df["magnitude"].map(
        lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
    )
    sig_df["depth_display"] = sig_df["depth_km"].map(
        lambda x: f"{x:.1f} km" if pd.notna(x) else "N/A"
    )

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

    st.markdown(
        f'<div class="sig-table-wrap"><table class="sig-table"><thead><tr><th>Place</th><th>Magnitude</th><th>Depth</th><th>Time</th><th>Link</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def render_sidebar_metrics(df: pd.DataFrame) -> None:
    """Render quick-glance metrics in the sidebar."""
    st.sidebar.subheader("Summary")
    mags = pd.to_numeric(df["magnitude"], errors="coerce")
    avg_mag = mags.mean()
    max_mag = mags.max()
    m1, m2, m3 = st.sidebar.columns(3)
    m1.metric("Quakes", int(len(df)))
    m2.metric("Avg Mag", f"{avg_mag:.1f}" if pd.notna(avg_mag) else "N/A")
    m3.metric("Max Mag", f"{max_mag:.1f}" if pd.notna(max_mag) else "N/A")
    tsunami_count = int((df["tsunami"] == 1).sum()) if "tsunami" in df.columns else 0
    st.sidebar.metric("Tsunami Advisories", tsunami_count)
