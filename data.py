"""
Data layer for the Global Disaster Monitor.

Fetches earthquake data from the USGS Earthquake Catalog API, parses it into
a pandas DataFrame, saves the raw QuakeML XML for XSLT transformation, and
caches results to CSV so the dashboard stays usable during network outages.
"""

import logging
import os
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st

from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

CONFIG = {
    # USGS Earthquake Catalog API
    "api_base": "https://earthquake.usgs.gov/fdsnws/event/1/query",
    "default_min_magnitude": 2.5,
    "cache_file": "USGS_cache.csv",
    "xml_output_file": "earthquakes.xml",
    "cache_ttl": 600,

    # UI defaults
    "default_days_back": 30,
    "map_points_min": 20,
    "map_points_max": 500,
    "map_points_default": 200,

    # Chart sizing
    "chart_height_small": 369,
    "chart_height_medium": 500,
    "sidebar_table_height": 387,
    "figsize_standard": (10, 5),
    "figsize_square": (6, 6),
    "figsize_wide": (10, 4),
}

# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _mag_to_alert_level(mag):
    """Derive an alert level from earthquake magnitude for dashboard display."""
    if pd.isna(mag):
        return "Unknown"
    if mag >= 7.0:
        return "Red"
    if mag >= 5.5:
        return "Orange"
    if mag >= 4.0:
        return "Green"
    return "Green"


def _extract_country(place_str: str) -> str:
    """Extract the country/region from a USGS place string like '7 km E of Lakatoro, Vanuatu'."""
    if not place_str:
        return "Unknown"
    parts = place_str.rsplit(",", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return place_str.strip()


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

@st.cache_data(ttl=CONFIG["cache_ttl"])
def fetch_usgs_geojson(from_date: str, to_date: str, min_magnitude: float = None) -> dict:
    """
    Fetch earthquake data from USGS in GeoJSON format.

    Parameters
    ----------
    from_date     : str   Start date (YYYY-MM-DD)
    to_date       : str   End date (YYYY-MM-DD)
    min_magnitude : float Minimum magnitude filter (default from CONFIG)
    """
    if min_magnitude is None:
        min_magnitude = CONFIG["default_min_magnitude"]

    params = {
        "format": "geojson",
        "starttime": from_date,
        "endtime": to_date,
        "minmagnitude": min_magnitude,
        "orderby": "time",
    }
    r = requests.get(CONFIG["api_base"], params=params, timeout=30)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=CONFIG["cache_ttl"])
def fetch_usgs_xml(from_date: str, to_date: str, min_magnitude: float = None) -> str:
    """
    Fetch the same earthquake data from USGS in QuakeML XML format.
    This XML file is saved to disk so the user can apply XSLT transformations.
    """
    if min_magnitude is None:
        min_magnitude = CONFIG["default_min_magnitude"]

    params = {
        "format": "xml",
        "starttime": from_date,
        "endtime": to_date,
        "minmagnitude": min_magnitude,
        "orderby": "time",
    }
    r = requests.get(CONFIG["api_base"], params=params, timeout=30)
    r.raise_for_status()
    return r.text


def save_raw_xml(xml_text: str):
    """Save the raw QuakeML XML to disk for XSLT transformation."""
    try:
        with open(CONFIG["xml_output_file"], "w", encoding="utf-8") as f:
            f.write(xml_text)
        logger.info("Saved raw XML to %s", CONFIG["xml_output_file"])
    except OSError as e:
        logger.warning("Could not write XML file: %s", e)


def geojson_to_df(data: dict) -> pd.DataFrame:
    """Convert USGS GeoJSON response into a cleaned DataFrame."""
    features = data.get("features", [])
    rows = []

    for feat in features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [None, None, None])

        # USGS timestamps are in milliseconds since epoch
        time_ms = props.get("time")
        if time_ms:
            dt = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
        else:
            dt = pd.NaT

        mag = props.get("mag")
        place = props.get("place", "")

        rows.append({
            "title": props.get("title", place),
            "link": props.get("url", ""),
            "event_type": props.get("type", "earthquake").capitalize(),
            "alert_level": _mag_to_alert_level(mag),
            "country": _extract_country(place),
            "magnitude": mag,
            "magnitude_type": props.get("magType", ""),
            "depth_km": coords[2] if len(coords) > 2 else None,
            "latitude": coords[1] if len(coords) > 1 else None,
            "longitude": coords[0] if len(coords) > 0 else None,
            "place": place,
            "alert_score": props.get("sig"),  # USGS "significance" score (0-1000+)
            "tsunami": props.get("tsunami", 0),
            "felt": props.get("felt"),
            "status": props.get("status", ""),
            "main_time": dt,
            "severity_text": f"M{mag}" if mag else "",
            "population_text": f"Felt by {props.get('felt', 0) or 0}" if props.get("felt") else "",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["date_utc"] = df["main_time"].dt.date
    df = df.sort_values("main_time", ascending=True)

    # Fill NaN in categorical columns
    for col in ["event_type", "alert_level", "country"]:
        df[col] = df[col].fillna("Unknown")

    return df


def load_data_with_cache(from_date: str = None, to_date: str = None, min_magnitude: float = None):
    """Fetch USGS earthquake data and cache to CSV. Falls back to cache on failure.

    Parameters
    ----------
    from_date     : str   YYYY-MM-DD start date
    to_date       : str   YYYY-MM-DD end date
    min_magnitude : float Minimum magnitude filter
    """
    try:
        # Fetch GeoJSON for easy DataFrame parsing
        geojson = fetch_usgs_geojson(from_date, to_date, min_magnitude)
        df = geojson_to_df(geojson)

        # Also fetch & save the XML version for XSLT use
        try:
            xml_text = fetch_usgs_xml(from_date, to_date, min_magnitude)
            save_raw_xml(xml_text)
        except Exception as e:
            logger.warning("Could not fetch/save XML: %s", e)

        # Write CSV cache
        try:
            df.to_csv(CONFIG["cache_file"], index=False, encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write cache file: %s", e)

        return df, None

    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning("USGS fetch failed: %s", e)

        if os.path.exists(CONFIG["cache_file"]):
            cached = pd.read_csv(CONFIG["cache_file"], encoding="utf-8")

            dt_cols = ["main_time"]
            for c in dt_cols:
                if c in cached.columns:
                    cached[c] = pd.to_datetime(cached[c], utc=True, errors="coerce")

            if "date_utc" in cached.columns:
                cached["date_utc"] = pd.to_datetime(cached["date_utc"], errors="coerce").dt.date

            for col in ["event_type", "alert_level", "country"]:
                if col in cached.columns:
                    cached[col] = cached[col].fillna("Unknown")

            return cached, "⚠️ USGS fetch failed — using cached data."

        return pd.DataFrame(), "⚠️ USGS fetch failed and no cache found."