
import plotly.graph_objects as go
import streamlit as st
from constants import PLOTLY_THEME_COLORS, PLOTLY_FONT

# ---------- Plotly Dark Theme Configuration ----------

DARK_BG = "#0f172a"
DARK_FG = "#e5e7eb"
DARK_GRID = "#334155"

def apply_plotly_theme(fig: go.Figure) -> go.Figure:
    """
    Apply a consistent dark theme, font, and grid layout to a Plotly figure.
    """
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font=dict(family=PLOTLY_FONT, color=DARK_FG, size=12),
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hoverlabel=dict(
            bgcolor="#1e293b",
            font_size=13,
            font_family=PLOTLY_FONT,
        ),
        colorway=PLOTLY_THEME_COLORS,
    )
    
    # Grid and axis styling
    fig.update_xaxes(
        showgrid=True,
        gridcolor=DARK_GRID,
        gridwidth=1,
        zeroline=False,
        tickfont=dict(color="#94a3b8"),
        title_font=dict(size=13, color=DARK_FG),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=DARK_GRID,
        gridwidth=1,
        zeroline=False,
        tickfont=dict(color="#94a3b8"),
        title_font=dict(size=13, color=DARK_FG),
    )
    
    return fig

def render_plotly_chart(fig: go.Figure, key: str | None = None) -> None:
    """Apply theme and render the plotly chart in Streamlit."""
    apply_plotly_theme(fig)
    st.plotly_chart(fig, width='stretch', key=key, theme=None)
