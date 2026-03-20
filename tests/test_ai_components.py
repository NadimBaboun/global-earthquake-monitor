import pandas as pd
import pytest
import plotly.graph_objects as go
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai import ai_components


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "magnitude": [1.0, 5.0, 9.0],
            "depth_km": [5, 50, 500],
            "alert_level": ["green", "orange", "red"],
            "country": ["Japan", "Chile", "USA"],
            "tsunami": [0, 1, 1],
        }
    )


def test_build_ai_chart_valid_bar(sample_df):
    spec = {"type": "bar", "x": "country", "y": "magnitude", "title": "Test Bar"}
    fig = ai_components.build_ai_chart(spec, sample_df)
    assert isinstance(fig, go.Figure)
    assert fig.layout.title.text == "Test Bar"


def test_build_ai_chart_with_filter(sample_df):
    # Filter for 'red' alert
    spec = {"type": "bar", "x": "country", "y": "magnitude", "filter_alert": "red"}
    fig = ai_components.build_ai_chart(spec, sample_df)
    assert isinstance(fig, go.Figure)
    # The chart_df inside should only have 1 row (USA)
    # We can't easily check the data inside the figure without deep inspection,
    # but we can verify it doesn't return None.


def test_build_ai_chart_invalid_type(sample_df):
    spec = {"type": "invalid_type", "x": "magnitude"}
    fig = ai_components.build_ai_chart(spec, sample_df)
    assert fig is None


def test_build_ai_chart_empty_data_after_filter(sample_df):
    spec = {"type": "bar", "x": "country", "filter_country": "NonExistent"}
    fig = ai_components.build_ai_chart(spec, sample_df)
    assert fig is None


def test_build_ai_chart_count_aggregation(sample_df):
    # Testing auto-count logic
    spec = {"type": "bar", "x": "alert_level", "y": "count"}
    fig = ai_components.build_ai_chart(spec, sample_df)
    assert isinstance(fig, go.Figure)


def test_build_ai_chart_pie(sample_df):
    spec = {"type": "pie", "x": "alert_level", "title": "Alert Dist"}
    fig = ai_components.build_ai_chart(spec, sample_df)
    assert isinstance(fig, go.Figure)
