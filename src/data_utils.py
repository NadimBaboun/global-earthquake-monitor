"""
Shared utility functions for earthquake data processing.
"""

import re
import pandas as pd
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

def mag_to_alert_level(mag: float | int | None) -> str:
    """Derive an alert level from earthquake magnitude."""
    if mag is None or pd.isna(mag):
        return "Unknown"
    mag_f = float(mag)
    if mag_f >= 7.0:
        return "Red"
    if mag_f >= 5.5:
        return "Orange"
    if mag_f >= 4.0:
        return "Yellow"
    return "Green"

def extract_country(place_str: str) -> str:
    """Extract country/region from a USGS place string."""
    if not place_str:
        return "Unknown"
    parts = place_str.rsplit(",", 1)
    return parts[1].strip() if len(parts) == 2 else place_str.strip()

def extract_magnitude(text: str) -> float | None:
    """Extract magnitude from text using regex."""
    patterns = [r"\bM\s*([0-9]+(?:\.[0-9]+)?)\b", r"\bMagnitude[:\s]*([0-9]+(?:\.[0-9]+)?)\b"]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None

def parse_rfc_datetime(value: str) -> datetime | pd.Timestamp:
    """Parse RSS pubDate-style timestamps."""
    if not value:
        return pd.NaT
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return pd.NaT

def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent DataFrame schema across all providers."""
    expected = {
        "title": "", "link": "", "event_type": "Earthquake", "alert_level": "Unknown",
        "country": "Unknown", "magnitude": None, "magnitude_type": "", "depth_km": None,
        "latitude": None, "longitude": None, "place": "", "alert_score": None,
        "tsunami": 0, "felt": None, "status": "", "main_time": pd.NaT,
        "severity_text": "", "population_text": "", "source": "Unknown",
    }
    for col, default_value in expected.items():
        if col not in df.columns:
            df[col] = default_value
            
    # Explicitly casting key columns to avoid dtype inference ambiguity 
    # (Fixes Pandas FuturesWarnings about all-NA columns during concat)
    numeric_cols = ["magnitude", "depth_km", "latitude", "longitude", "alert_score", "felt"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
    df["main_time"] = pd.to_datetime(df["main_time"], utc=True, errors="coerce")
    df["date_utc"] = df["main_time"].dt.date
    for col in ["event_type", "alert_level", "country", "source"]:
        df[col] = df[col].fillna("Unknown").astype(str)
    return df
