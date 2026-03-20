import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils import data_utils


def test_mag_to_alert_level():
    assert data_utils.mag_to_alert_level(7.5) == "Red"
    assert data_utils.mag_to_alert_level(6.0) == "Orange"
    assert data_utils.mag_to_alert_level(4.5) == "Yellow"
    assert data_utils.mag_to_alert_level(2.0) == "Green"
    assert data_utils.mag_to_alert_level(None) == "Unknown"
    assert data_utils.mag_to_alert_level(float("nan")) == "Unknown"


def test_extract_country():
    assert data_utils.extract_country("10km N of Tokyo, Japan") == "Japan"
    assert data_utils.extract_country("California") == "California"
    assert data_utils.extract_country("") == "Unknown"
    assert data_utils.extract_country(None) == "Unknown"


def test_extract_magnitude():
    assert data_utils.extract_magnitude("M 5.6 - Test") == 5.6
    assert data_utils.extract_magnitude("Magnitude: 7.2") == 7.2
    assert data_utils.extract_magnitude("No magnitude here") is None


def test_compute_daily_aggregates():
    df = pd.DataFrame(
        {
            "date_utc": [pd.Timestamp("2024-01-01").date()] * 3,
            "magnitude": [5.0, 6.0, 7.0],
        }
    )
    counts, avgs, daily_eng, cumuls_eng = data_utils.compute_daily_aggregates(df)

    assert counts.iloc[0] == 3
    assert avgs.iloc[0] == 6.0
    assert cumuls_eng.iloc[0] == (10**7.5 + 10**9.0 + 10**10.5)


def test_normalize_schema_fills_missing():
    df = pd.DataFrame({"magnitude": [5.0]})
    normalized = data_utils.normalize_schema(df)

    assert "alert_level" in normalized.columns
    assert "source" in normalized.columns
    assert normalized["alert_level"].iloc[0] == "Unknown"
    assert normalized["source"].iloc[0] == "Unknown"
