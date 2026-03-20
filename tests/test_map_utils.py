import sys
from pathlib import Path
import pandas as pd
import pytest

# Add 'src' to sys.path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.map_utils import _prepare_map_data
from constants import ALERT_RGBA_COLORS, DEFAULT_ALERT_RGBA


@pytest.fixture
def sample_map_df():
    return pd.DataFrame(
        [
            {
                "magnitude": 7.5,
                "alert_level": "Red",
                "tsunami": 1,
                "main_time": pd.to_datetime("2024-03-15T12:00:00Z"),
                "depth_km": 10.5,
            },
            {
                "magnitude": 4.0,
                "alert_level": "Yellow",
                "tsunami": 0,
                "main_time": pd.to_datetime("2024-03-15T13:00:00Z"),
                "depth_km": 35.0,
            },
            {
                "magnitude": 3.0,
                "alert_level": "Unknown",
                "tsunami": 0,
                "main_time": pd.to_datetime("2024-03-15T14:00:00Z"),
                "depth_km": 5.0,
            },
        ]
    )


def test_prepare_map_data_colors(sample_map_df):
    processed = _prepare_map_data(sample_map_df)

    # Red alert check
    red_row = processed.iloc[0]
    expected_red = ALERT_RGBA_COLORS["Red"]
    assert red_row["color_r"] == expected_red[0]
    assert red_row["color_g"] == expected_red[1]
    assert red_row["color_b"] == expected_red[2]

    # Unknown alert check (default)
    unknown_row = processed.iloc[2]
    assert unknown_row["color_r"] == DEFAULT_ALERT_RGBA[0]


def test_prepare_map_data_radius(sample_map_df):
    processed = _prepare_map_data(sample_map_df)

    # Magnitude 7.5 should have larger radius than magnitude 4.0
    assert processed.iloc[0]["radius"] > processed.iloc[1]["radius"]

    # Small magnitudes should still have minimum radius (3000)
    # 2**(3-1) * 2000 = 8000 (larger than 3000)
    # Let's test absolute minimum with a very small magnitude
    tiny_df = pd.DataFrame(
        [
            {
                "magnitude": 0.5,
                "alert_level": "Green",
                "tsunami": 0,
                "main_time": pd.to_datetime("now"),
                "depth_km": 10,
            }
        ]
    )
    processed_tiny = _prepare_map_data(tiny_df)
    assert processed_tiny.iloc[0]["radius"] == 3000


def test_prepare_map_data_tsunami_styling(sample_map_df):
    processed = _prepare_map_data(sample_map_df)

    # Tsunami = 1 should have specific line color and width
    tsunami_row = processed.iloc[0]
    assert tsunami_row["line_width"] == 3
    assert tsunami_row["line_r"] == 56  # Custom cyan-ish highlight

    # Tsunami = 0 should have default styling
    normal_row = processed.iloc[1]
    assert normal_row["line_width"] == 1
    assert normal_row["line_r"] == 255
