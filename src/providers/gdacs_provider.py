"""
GDACS data provider for the Global Earthquake Monitor.
"""

import logging
import requests
import xml.etree.ElementTree as ET
import pandas as pd

logger = logging.getLogger(__name__)


def fetch_gdacs_xml(rss_url: str) -> str:
    """Fetch GDACS earthquake RSS/XML feed."""
    r = requests.get(rss_url, timeout=30)
    r.raise_for_status()
    return r.text


def save_gdacs_xml(xml_text: str, output_path: str) -> None:
    """Persist GDACS raw XML for cache/debug usage."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_text)
    except OSError as e:
        logger.warning("Could not write GDACS XML file: %s", e)


def gdacs_xml_to_df(
    xml_text: str,
    start_date: str | None,
    end_date: str | None,
    min_mag: float | None,
    extract_mag_fn,
    parse_dt_fn,
) -> pd.DataFrame:
    """Parse GDACS RSS/XML into the same schema used by USGS data."""
    root = ET.fromstring(xml_text)
    rows = []
    ns = {
        "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "gdacs": "http://www.gdacs.org",
    }
    start_ts = (
        pd.to_datetime(start_date, utc=True, errors="coerce") if start_date else None
    )
    end_ts = pd.to_datetime(end_date, utc=True, errors="coerce") if end_date else None

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = parse_dt_fn((item.findtext("pubDate") or "").strip())
        event_type = (
            item.findtext("gdacs:eventtype", default="Earthquake", namespaces=ns)
            or "Earthquake"
        ).capitalize()
        country = (
            item.findtext("gdacs:country", default="", namespaces=ns) or ""
        ).strip() or "Unknown"
        gdacs_alert = (
            (item.findtext("gdacs:alertlevel", default="", namespaces=ns) or "")
            .strip()
            .capitalize()
        )
        alert_level = (
            gdacs_alert
            if gdacs_alert in {"Red", "Orange", "Yellow", "Green"}
            else "Unknown"
        )
        status = (
            item.findtext("gdacs:episodealertlevel", default="", namespaces=ns) or ""
        ).strip()
        place = (
            item.findtext("gdacs:location", default="", namespaces=ns) or ""
        ).strip()
        if not place:
            place = title

        magnitude = extract_mag_fn(title) or extract_mag_fn(desc)
        if magnitude is None:
            mag_text = (
                item.findtext("gdacs:magnitude", default="", namespaces=ns) or ""
            ).strip()
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
        if (
            end_ts is not None
            and pd.notna(pub_date)
            and pub_date > end_ts + pd.Timedelta(days=1)
        ):
            continue
        if min_mag is not None and magnitude is not None and magnitude < float(min_mag):
            continue

        rows.append(
            {
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
            }
        )

    df = pd.DataFrame(rows)
    return df
