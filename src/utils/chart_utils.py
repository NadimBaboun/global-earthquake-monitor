import plotly.graph_objects as go
import streamlit as st

# Thematic constants used by tests
DARK_BG = "rgba(0,0,0,0)"
DARK_FG = "#e2e8f0"


def apply_plotly_theme(fig: go.Figure) -> None:
    """Apply the standard dark dashboard theme to a Plotly figure."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font=dict(color=DARK_FG),
        margin=dict(l=20, r=20, t=40, b=20),
    )


def render_plotly_chart(fig: go.Figure, key: str = None) -> None:
    """Standardized wrapper for rendering Plotly charts with a dark theme."""
    apply_plotly_theme(fig)
    # Using width="stretch" for modern Streamlit compatibility
    st.plotly_chart(fig, width="stretch", key=key)
