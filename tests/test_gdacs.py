import sys
from pathlib import Path
import pytest

# Add 'src' to sys.path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from providers import gdacs_provider
from utils.data_utils import extract_magnitude, parse_rfc_datetime


@pytest.fixture
def sample_gdacs_xml():
    return """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#" xmlns:gdacs="http://www.gdacs.org">
  <channel>
    <item>
      <title>M 6.8 Earthquake in Japan</title>
      <link>https://www.gdacs.org/report.aspx?eventid=12345</link>
      <description>Magnitude 6.8 M, depth 10km, alert level Red.</description>
      <pubDate>Fri, 15 Mar 2024 12:00:00 GMT</pubDate>
      <geo:lat>35.0</geo:lat>
      <geo:long>139.0</geo:long>
      <gdacs:eventtype>Earthquake</gdacs:eventtype>
      <gdacs:alertlevel>Red</gdacs:alertlevel>
      <gdacs:country>Japan</gdacs:country>
      <gdacs:location>Off the coast of Honshu</gdacs:location>
    </item>
    <item>
      <title>Earthquake in Testland</title>
      <link>https://www.gdacs.org/report.aspx?eventid=67890</link>
      <description>Small earthquake, no magnitude listed in text.</description>
      <pubDate>Fri, 15 Mar 2024 13:00:00 GMT</pubDate>
      <geo:lat>10.0</geo:lat>
      <geo:long>20.0</geo:long>
      <gdacs:eventtype>Earthquake</gdacs:eventtype>
      <gdacs:alertlevel>Green</gdacs:alertlevel>
      <gdacs:country>Testland</gdacs:country>
      <gdacs:magnitude>4.5</gdacs:magnitude>
    </item>
  </channel>
</rss>
"""


def test_gdacs_xml_to_df_extracts_correct_fields(sample_gdacs_xml):
    df = gdacs_provider.gdacs_xml_to_df(
        sample_gdacs_xml,
        start_date=None,
        end_date=None,
        min_mag=None,
        extract_mag_fn=extract_magnitude,
        parse_dt_fn=parse_rfc_datetime,
    )

    assert len(df) == 2

    # Check first item (magnitude in title)
    row1 = df[df["country"] == "Japan"].iloc[0]
    assert row1["magnitude"] == 6.8
    assert row1["alert_level"] == "Red"
    assert row1["latitude"] == 35.0
    assert row1["longitude"] == 139.0
    assert row1["source"] == "GDACS"

    # Check second item (magnitude in gdacs:magnitude)
    row2 = df[df["country"] == "Testland"].iloc[0]
    assert row2["magnitude"] == 4.5
    assert row2["alert_level"] == "Green"
    assert row2["source"] == "GDACS"


def test_gdacs_xml_to_df_filtering(sample_gdacs_xml):
    # Filter by date
    from_date = "2024-03-15T12:30:00Z"
    df = gdacs_provider.gdacs_xml_to_df(
        sample_gdacs_xml,
        start_date=from_date,
        end_date=None,
        min_mag=None,
        extract_mag_fn=extract_magnitude,
        parse_dt_fn=parse_rfc_datetime,
    )
    assert len(df) == 1
    assert df.iloc[0]["country"] == "Testland"

    # Filter by magnitude
    df_mag = gdacs_provider.gdacs_xml_to_df(
        sample_gdacs_xml,
        start_date=None,
        end_date=None,
        min_mag=6.0,
        extract_mag_fn=extract_magnitude,
        parse_dt_fn=parse_rfc_datetime,
    )
    assert len(df_mag) == 1
    assert df_mag.iloc[0]["country"] == "Japan"


def test_gdacs_xml_to_df_malformed_coords():
    malformed_xml = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
  <channel>
    <item>
      <title>M 5.0 - Test</title>
      <geo:lat>not_a_number</geo:lat>
      <geo:long>20.0</geo:long>
    </item>
  </channel>
</rss>
"""
    df = gdacs_provider.gdacs_xml_to_df(
        malformed_xml,
        start_date=None,
        end_date=None,
        min_mag=None,
        extract_mag_fn=extract_magnitude,
        parse_dt_fn=parse_rfc_datetime,
    )
    assert len(df) == 1
    assert df.iloc[0]["latitude"] is None
    assert df.iloc[0]["longitude"] == 20.0
