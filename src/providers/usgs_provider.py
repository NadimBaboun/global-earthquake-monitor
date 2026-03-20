"""
USGS data provider for the Global Earthquake Monitor.
"""

import logging
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def fetch_usgs_geojson(
    api_base: str,
    start_date: str | None,
    end_date: str | None,
    min_mag: float,
) -> dict[str, Any]:
    """Fetch earthquake data from USGS in GeoJSON format."""
    params = {
        "format": "geojson",
        "starttime": start_date,
        "endtime": end_date,
        "minmagnitude": min_mag,
        "orderby": "time",
    }
    r = requests.get(api_base, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_usgs_xml(
    api_base: str,
    start_date: str | None,
    end_date: str | None,
    min_mag: float,
) -> str:
    """Fetch earthquake data from USGS in QuakeML XML format."""
    params = {
        "format": "xml",
        "starttime": start_date,
        "endtime": end_date,
        "minmagnitude": min_mag,
        "orderby": "time",
    }
    r = requests.get(api_base, params=params, timeout=30)
    r.raise_for_status()
    return r.text


def save_raw_xml(xml_text: str, output_path: str) -> None:
    """Save the raw QuakeML XML to disk with an XSLT processing instruction."""
    PI = '<?xml-stylesheet type="text/xsl" href="xml/quakeml_to_map.xsl"?>'
    try:
        if xml_text.startswith("<?xml"):
            end_of_decl = xml_text.index("?>") + 2
            xml_text = xml_text[:end_of_decl] + "\n" + PI + xml_text[end_of_decl:]
        else:
            xml_text = PI + "\n" + xml_text

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_text)
        logger.info("Saved raw XML to %s", output_path)
    except OSError as e:
        logger.warning("Could not write XML file: %s", e)


def geojson_to_df(
    data: dict[str, Any], mag_to_alert_fn, extract_country_fn
) -> pd.DataFrame:
    """Convert USGS GeoJSON response into a cleaned DataFrame."""
    features = data.get("features", [])
    rows = []

    for feat in features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [None, None, None])

        time_ms = props.get("time")
        if time_ms:
            dt = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
        else:
            dt = pd.NaT

        mag = props.get("mag")
        place = props.get("place", "")

        rows.append(
            {
                "title": props.get("title", place),
                "link": props.get("url", ""),
                "event_type": props.get("type", "earthquake").capitalize(),
                "alert_level": mag_to_alert_fn(mag),
                "country": extract_country_fn(place),
                "magnitude": mag,
                "magnitude_type": props.get("magType", ""),
                "depth_km": coords[2] if len(coords) > 2 else None,
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if len(coords) > 0 else None,
                "place": place,
                "alert_score": props.get("sig"),
                "tsunami": props.get("tsunami", 0),
                "felt": props.get("felt"),
                "status": props.get("status", ""),
                "main_time": dt,
                "severity_text": f"M{mag}" if mag else "",
                "population_text": f"Felt by {props.get('felt', 0) or 0}"
                if props.get("felt")
                else "",
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["source"] = "USGS"
    return df
