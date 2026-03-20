from pathlib import Path
import sys
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils import chart_utils  # noqa: E402


def test_apply_plotly_theme_sets_background():
    fig = go.Figure()
    chart_utils.apply_plotly_theme(fig)

    assert fig.layout.paper_bgcolor == chart_utils.DARK_BG
    assert fig.layout.plot_bgcolor == chart_utils.DARK_BG
    assert fig.layout.font.color == chart_utils.DARK_FG


def test_render_plotly_chart_calls_streamlit(monkeypatch):
    called = {"count": 0}

    def fake_plotly_chart(fig, *args, **kwargs):
        called["count"] += 1

    monkeypatch.setattr(st, "plotly_chart", fake_plotly_chart)

    fig = go.Figure()
    chart_utils.render_plotly_chart(fig)

    assert called["count"] == 1
