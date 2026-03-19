"""
Data layer for the Global Earthquake Monitor.

Fetches earthquake data from the USGS Earthquake Catalog API, parses it into
a pandas DataFrame, saves the raw QuakeML XML for XSLT transformation, and
caches results to CSV so the dashboard stays usable during network outages.
"""

import logging
import os
import re
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
import tempfile

_tmp = tempfile.gettempdir()

CONFIG = {
    # USGS Earthquake Catalog API
    "api_base": "https://earthquake.usgs.gov/fdsnws/event/1/query",
    "gdacs_rss_url": "https://www.gdacs.org/xml/rss.xml",
    "default_min_magnitude": 2.5,
    "cache_file": os.path.join(_tmp, "USGS_cache.csv"),
    "gdacs_cache_file": os.path.join(_tmp, "GDACS_cache.csv"),
    "xml_output_file": os.path.join(_tmp, "earthquakes.xml"),
    "gdacs_xml_output_file": os.path.join(_tmp, "GDACS_data.xml"),
    "cache_ttl": 600,

    # UI defaults
    "default_days_back": 30,
    "map_points_min": 20,
    "map_points_max": 500,
    "map_points_default": 200,
    "histogram_bins": 20,

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
        return "Yellow"
    return "Green"


def _extract_country(place_str: str) -> str:
    """Extract the country/region from a USGS place string like '7 km E of Lakatoro, Vanuatu'."""
    if not place_str:
        return "Unknown"
    parts = place_str.rsplit(",", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return place_str.strip()


def _extract_magnitude(text: str):
    """Extract magnitude like 'M 6.2' or 'Magnitude 6.2' from text."""
    if not text:
        return None
    patterns = [
        r"\bM\s*([0-9]+(?:\.[0-9]+)?)\b",
        r"\bMagnitude[:\s]*([0-9]+(?:\.[0-9]+)?)\b",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
    return None


def _parse_rfc_datetime(value: str):
    """Parse RSS pubDate-style timestamps into UTC datetimes."""
    if not value:
        return pd.NaT
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return pd.NaT


def _normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure both USGS and GDACS data share the same DataFrame schema."""
    expected = {
        "title": "",
        "link": "",
        "event_type": "Earthquake",
        "alert_level": "Unknown",
        "country": "Unknown",
        "magnitude": None,
        "magnitude_type": "",
        "depth_km": None,
        "latitude": None,
        "longitude": None,
        "place": "",
        "alert_score": None,
        "tsunami": 0,
        "felt": None,
        "status": "",
        "main_time": pd.NaT,
        "severity_text": "",
        "population_text": "",
        "source": "Unknown",
    }
    for col, default_value in expected.items():
        if col not in df.columns:
            df[col] = default_value

    df["main_time"] = pd.to_datetime(df["main_time"], utc=True, errors="coerce")
    df["date_utc"] = df["main_time"].dt.date
    for col in ["event_type", "alert_level", "country", "source"]:
        df[col] = df[col].fillna("Unknown")

    return df


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

@st.cache_data(ttl=CONFIG["cache_ttl"], show_spinner=False)
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


@st.cache_data(ttl=CONFIG["cache_ttl"], show_spinner=False)
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
    """Save the raw QuakeML XML to disk for XSLT transformation.

    Injects an ``xml-stylesheet`` processing instruction so that opening
    ``earthquakes.xml`` in a browser automatically applies the XSLT
    and renders the interactive Leaflet map.
    """
    PI = '<?xml-stylesheet type="text/xsl" href="xml/quakeml_to_map.xsl"?>'
    try:
        # Insert PI right after the XML declaration
        if xml_text.startswith("<?xml"):
            end_of_decl = xml_text.index("?>") + 2
            xml_text = xml_text[:end_of_decl] + "\n" + PI + xml_text[end_of_decl:]
        else:
            xml_text = PI + "\n" + xml_text

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

    df["source"] = "USGS"
    df = _normalize_schema(df)
    df = df.sort_values("main_time", ascending=True)
    return df


@st.cache_data(ttl=CONFIG["cache_ttl"], show_spinner=False)
def fetch_gdacs_xml() -> str:
    """Fetch GDACS earthquake RSS/XML feed."""
    r = requests.get(CONFIG["gdacs_rss_url"], timeout=30)
    r.raise_for_status()
    return r.text


def save_gdacs_xml(xml_text: str):
    """Persist GDACS raw XML for cache/debug usage."""
    try:
        with open(CONFIG["gdacs_xml_output_file"], "w", encoding="utf-8") as f:
            f.write(xml_text)
    except OSError as e:
        logger.warning("Could not write GDACS XML file: %s", e)


def gdacs_xml_to_df(xml_text: str, from_date: str = None, to_date: str = None, min_magnitude: float = None) -> pd.DataFrame:
    """Parse GDACS RSS/XML into the same schema used by USGS data."""
    root = ET.fromstring(xml_text)
    rows = []
    ns = {
        "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "gdacs": "http://www.gdacs.org",
    }
    start_ts = pd.to_datetime(from_date, utc=True, errors="coerce") if from_date else None
    end_ts = pd.to_datetime(to_date, utc=True, errors="coerce") if to_date else None

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = _parse_rfc_datetime((item.findtext("pubDate") or "").strip())
        event_type = (item.findtext("gdacs:eventtype", default="Earthquake", namespaces=ns) or "Earthquake").capitalize()
        country = (item.findtext("gdacs:country", default="", namespaces=ns) or "").strip() or "Unknown"
        gdacs_alert = (item.findtext("gdacs:alertlevel", default="", namespaces=ns) or "").strip().capitalize()
        alert_level = gdacs_alert if gdacs_alert in {"Red", "Orange", "Yellow", "Green"} else "Unknown"
        status = (item.findtext("gdacs:episodealertlevel", default="", namespaces=ns) or "").strip()
        place = (item.findtext("gdacs:location", default="", namespaces=ns) or "").strip()
        if not place:
            place = title

        magnitude = _extract_magnitude(title) or _extract_magnitude(desc)
        if magnitude is None:
            mag_text = (item.findtext("gdacs:magnitude", default="", namespaces=ns) or "").strip()
            try:
                magnitude = float(mag_text) if mag_text else None
            except ValueError:
                magnitude = None

        lat_text = (item.findtext("geo:lat", default="", namespaces=ns) or "").strip()
        lon_text = (item.findtext("geo:long", default="", namespaces=ns) or "").strip()
        try:
            latitude = float(lat_text) if lat_text else None
        except ValueError:
            latitude = None
        try:
            longitude = float(lon_text) if lon_text else None
        except ValueError:
            longitude = None

        if start_ts is not None and pd.notna(pub_date) and pub_date < start_ts:
            continue
        if end_ts is not None and pd.notna(pub_date) and pub_date > end_ts + pd.Timedelta(days=1):
            continue
        if min_magnitude is not None and magnitude is not None and magnitude < float(min_magnitude):
            continue

        rows.append({
            "title": title or place,
            "link": link,
            "event_type": event_type,
            "alert_level": alert_level,
            "country": country,
            "magnitude": magnitude,
            "magnitude_type": "",
            "depth_km": None,
            "latitude": latitude,
            "longitude": longitude,
            "place": place,
            "alert_score": None,
            "tsunami": 0,
            "felt": None,
            "status": status,
            "main_time": pub_date,
            "severity_text": f"M{magnitude}" if magnitude is not None else "",
            "population_text": "",
            "source": "GDACS",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = _normalize_schema(df)
    df = df.sort_values("main_time", ascending=True)
    return df


def _load_cached_frame(path: str) -> pd.DataFrame:
    cached = pd.read_csv(path, encoding="utf-8")
    return _normalize_schema(cached)

def load_data_with_cache(from_date: str = None, to_date: str = None, min_magnitude: float = None):
    """Fetch USGS earthquake data and cache to CSV. Falls back to cache on failure.

    Parameters
    ----------
    from_date     : str   YYYY-MM-DD start date
    to_date       : str   YYYY-MM-DD end date
    min_magnitude : float Minimum magnitude filter
    """
    return load_data_by_source(from_date=from_date, to_date=to_date, min_magnitude=min_magnitude, source="USGS")


def _load_usgs_with_cache(from_date: str = None, to_date: str = None, min_magnitude: float = None):
    try:
        geojson = fetch_usgs_geojson(from_date, to_date, min_magnitude)
        df = geojson_to_df(geojson)

        try:
            xml_text = fetch_usgs_xml(from_date, to_date, min_magnitude)
            save_raw_xml(xml_text)
        except Exception as e:
            logger.warning("Could not fetch/save XML: %s", e)

        try:
            df.to_csv(CONFIG["cache_file"], index=False, encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write cache file: %s", e)

        return df, None
    except (requests.RequestException, ValueError, KeyError, ET.ParseError) as e:
        logger.warning("USGS fetch failed: %s", e)
        if os.path.exists(CONFIG["cache_file"]):
            return _load_cached_frame(CONFIG["cache_file"]), "⚠️ USGS fetch failed — using cached data."
        return pd.DataFrame(), "⚠️ USGS fetch failed and no cache found."


def _load_gdacs_with_cache(from_date: str = None, to_date: str = None, min_magnitude: float = None):
    try:
        xml_text = fetch_gdacs_xml()
        save_gdacs_xml(xml_text)
        df = gdacs_xml_to_df(xml_text, from_date=from_date, to_date=to_date, min_magnitude=min_magnitude)
        try:
            df.to_csv(CONFIG["gdacs_cache_file"], index=False, encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write GDACS cache file: %s", e)
        return df, None
    except (requests.RequestException, ValueError, KeyError, ET.ParseError) as e:
        logger.warning("GDACS fetch failed: %s", e)
        if os.path.exists(CONFIG["gdacs_cache_file"]):
            return _load_cached_frame(CONFIG["gdacs_cache_file"]), "⚠️ GDACS fetch failed — using cached data."
        return pd.DataFrame(), "⚠️ GDACS fetch failed and no cache found."


def load_data_by_source(
    from_date: str = None,
    to_date: str = None,
    min_magnitude: float = None,
    source: str = "USGS",
):
    """Load earthquake data from USGS, GDACS, or both using cache fallbacks."""
    selected = (source or "USGS").strip().upper()

    if selected == "USGS":
        return _load_usgs_with_cache(from_date=from_date, to_date=to_date, min_magnitude=min_magnitude)

    if selected == "GDACS":
        return _load_gdacs_with_cache(from_date=from_date, to_date=to_date, min_magnitude=min_magnitude)

    if selected == "BOTH":
        usgs_df, usgs_warn = _load_usgs_with_cache(from_date=from_date, to_date=to_date, min_magnitude=min_magnitude)
        gdacs_df, gdacs_warn = _load_gdacs_with_cache(from_date=from_date, to_date=to_date, min_magnitude=min_magnitude)

        frames = [f for f in [usgs_df, gdacs_df] if f is not None and not f.empty]
        if frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = _normalize_schema(merged).sort_values("main_time", ascending=True)
        else:
            merged = pd.DataFrame()

        warn_msgs = [w for w in [usgs_warn, gdacs_warn] if w]
        return merged, " | ".join(warn_msgs) if warn_msgs else None

    return pd.DataFrame(), f"⚠️ Unknown data source selection: {source}"