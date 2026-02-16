"""
Data layer for the Global Disaster Monitor.

Handles fetching the GDACS RSS feed, parsing its XML into a pandas DataFrame,
and caching results to CSV so the dashboard stays usable during network outages.
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
    # Data
    "rss_url": "https://www.gdacs.org/xml/rss.xml",
    "cache_file": "GDACS_cache.csv",
    "cache_ttl": 600,

    # UI defaults
    "default_days_back": 14,
    "map_points_min": 20,
    "map_points_max": 300,
    "map_points_default": 120,

    # Chart sizing
    "chart_height_small": 369,
    "chart_height_medium": 500,
    "sidebar_table_height": 387,
    "figsize_standard": (10, 5),
    "figsize_square": (6, 6),
    "figsize_wide": (10, 4),
}

# GDACS RSS uses custom XML namespaces; we register only the ones our XPath queries need
NS = {
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "gdacs": "http://www.gdacs.org",
}

# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _parse_rfc822(s: str):
    """Parse an RFC-822 date string (e.g. 'Wed, 17 Dec 2025 15:15:04 GMT') into a UTC datetime. Returns pd.NaT on failure."""
    if not s:
        return pd.NaT
    try:
        dt = datetime.strptime(s.strip(), "%a, %d %b %Y %H:%M:%S %Z")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return pd.NaT


def _find_text(el, path: str, default=None):
    """Extract the text of an XML sub-element at *path*, returning *default* if missing."""
    if el is None:
        return default
    node = el.find(path, NS)
    if node is None or node.text is None:
        return default
    return node.text.strip()


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

@st.cache_data(ttl=CONFIG["cache_ttl"])
def fetch_gdacs_rss_xml() -> str:
    """
    Fetch GDACS RSS.
    Some networks return HTML (blocked/redirect pages) instead of XML.
    Detect that early to avoid ElementTree's vague errors.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    }
    r = requests.get(CONFIG["rss_url"], timeout=30, headers=headers, allow_redirects=True)
    r.raise_for_status()

    # Decode bytes manually so we can strip the BOM some servers prepend
    text = r.content.decode("utf-8", errors="replace").lstrip("\ufeff").strip()
    head = text[:200].lower()

    if head.startswith("<!doctype html") or head.startswith("<html") or "<html" in head:
        raise ValueError(
            "GDACS returned HTML instead of XML (blocked/redirect/proxy page).\n"
            f"Status: {r.status_code}, Content-Type: {r.headers.get('content-type')}\n"
            f"First chars: {text[:200]}"
        )

    if not text.startswith("<"):
        raise ValueError(
            "Response does not look like XML.\n"
            f"Status: {r.status_code}, Content-Type: {r.headers.get('content-type')}\n"
            f"First chars: {text[:200]}"
        )

    return text


def rss_to_df(xml_text: str) -> pd.DataFrame:
    """Convert raw GDACS RSS XML into a cleaned DataFrame with typed columns and a unified event time."""
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")

    # Map each DataFrame column to (type, XML path, fallback).
    # We only extract fields the dashboard actually uses to keep the DataFrame lean.
    FIELDS = {
        "title": ("text", "title", ""),
        "link": ("text", "link", ""),
        "event_type": ("text", "gdacs:eventtype", "Unknown"),
        "alert_level": ("text", "gdacs:alertlevel", "Unknown"),
        "country": ("text", "gdacs:country", "Unknown"),
        "severity_text": ("text", "gdacs:severity", ""),
        "population_text": ("text", "gdacs:population", ""),
        "alert_score": ("num", "gdacs:alertscore", None),
        "latitude": ("num", "geo:Point/geo:lat", None),
        "longitude": ("num", "geo:Point/geo:long", None),
        "pub_date": ("date", "pubDate", None),
        "from_date": ("date", "gdacs:fromdate", None),
    }

    rows = []
    for it in items:
        row = {}
        for col, (kind, path, default) in FIELDS.items():
            if kind == "text":
                row[col] = _find_text(it, path, default)
            elif kind == "num":
                row[col] = pd.to_numeric(_find_text(it, path, default), errors="coerce")
            elif kind == "date":
                row[col] = _parse_rfc822(_find_text(it, path, default))
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # from_date is when the event actually started; pub_date is when GDACS published it.
    # We prefer from_date so daily charts reflect real event timing, not reporting delay.
    df["main_time"] = pd.to_datetime(df["from_date"].fillna(df["pub_date"]), utc=True, errors="coerce")
    df["date_utc"] = df["main_time"].dt.date
    df = df.sort_values("main_time", ascending=True)

    # Filters and groupby operations break on NaN; fill with "Unknown" so every row is usable
    for col in ["event_type", "alert_level", "country"]:
        df[col] = df[col].fillna("Unknown")

    return df


def load_data_with_cache():
    """Fetch live GDACS data and cache it to CSV. Falls back to the cached file on network failure."""
    try:
        xml_text = fetch_gdacs_rss_xml()
        df = rss_to_df(xml_text)

        # Write cache separately so a disk error doesn't prevent showing fresh data
        try:
            df.to_csv(CONFIG["cache_file"], index=False, encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write cache file: %s", e)

        return df, None

    except (requests.RequestException, ET.ParseError, ValueError) as e:
        logger.warning("GDACS fetch failed: %s", e)

        if os.path.exists(CONFIG["cache_file"]):
            cached = pd.read_csv(CONFIG["cache_file"], encoding="utf-8")

            # CSV loses datetime dtype; re-parse only the columns the dashboard needs
            dt_cols = ["pub_date", "from_date", "main_time"]
            for c in dt_cols:
                if c in cached.columns:
                    cached[c] = pd.to_datetime(cached[c], utc=True, errors="coerce")

            if "date_utc" in cached.columns:
                cached["date_utc"] = pd.to_datetime(cached["date_utc"], errors="coerce").dt.date

            for col in ["event_type", "alert_level", "country"]:
                if col in cached.columns:
                    cached[col] = cached[col].fillna("Unknown")

            return cached, "Error: GDACS fetch failed — using cached file."

        return pd.DataFrame(), "Error: GDACS fetch failed and no cache found."
