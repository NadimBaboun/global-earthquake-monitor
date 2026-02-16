from contextlib import contextmanager

import matplotlib.pyplot as plt
import streamlit as st

# ---------- Streamlit render helper ----------

def show_fig(fig):
    """Render a matplotlib figure in Streamlit and release its memory."""
    st.pyplot(fig, clear_figure=True)

# ---------- Matplotlib dark theme helpers ----------
DARK_BG = "#0f172a"
DARK_FG = "#e5e7eb"
DARK_GRID = "#334155"

def darken_fig(fig, ax):
    """Apply a consistent dark look to a matplotlib figure/axes."""
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=DARK_FG)
    for spine in ax.spines.values():
        spine.set_color(DARK_FG)
    ax.xaxis.label.set_color(DARK_FG)
    ax.yaxis.label.set_color(DARK_FG)
    ax.title.set_color(DARK_FG)
    ax.grid(True, color=DARK_GRID, alpha=0.35)

@contextmanager
def dark_chart(title="", xlabel="", ylabel="", figsize=None, legend=None, tight=True, rotate_x=False):
    """
    Context manager for dark-themed matplotlib charts.

    Yields (fig, ax). On exit it applies the dark theme, optional legend styling,
    tight_layout, and renders via show_fig.

    Parameters
    ----------
    title    : str   chart title
    xlabel   : str   x-axis label
    ylabel   : str   y-axis label
    figsize  : tuple figure size, defaults to (10, 5)
    legend   : str | None if set, adds a legend with this as the title
                            (pass "" for a legend with no title)
    tight    : bool  call tight_layout before rendering
    rotate_x : bool  rotate x-tick labels 45°
    """
    
    if figsize is None:
        figsize = (10, 5)

    with plt.style.context("dark_background"):
        fig, ax = plt.subplots(figsize=figsize)
        yield fig, ax

        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        if rotate_x:
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", color=DARK_FG)
        if legend is not None:
            leg = ax.legend(
                **({"title": legend, "bbox_to_anchor": (1.02, 1), "loc": "upper left"} if legend else {})
            )
            if leg is not None:
                plt.setp(leg.get_texts(), color=DARK_FG)
                if legend:
                    plt.setp(leg.get_title(), color=DARK_FG)

        darken_fig(fig, ax)
        if tight:
            plt.tight_layout()
        show_fig(fig)