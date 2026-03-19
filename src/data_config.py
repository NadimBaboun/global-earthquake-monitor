"""
Data-layer configuration for the Global Earthquake Monitor.
"""

import os

# Use a local .cache directory in the project root for persistence
_cache_dir = ".cache"

CONFIG = {
    "api_base": "https://earthquake.usgs.gov/fdsnws/event/1/query",
    "gdacs_rss_url": "https://www.gdacs.org/xml/rss.xml",
    "default_min_magnitude": 2.5,
    "cache_file": os.path.join(_cache_dir, "USGS_cache.csv"),
    "gdacs_cache_file": os.path.join(_cache_dir, "GDACS_cache.csv"),
    "xml_output_file": os.path.join(_cache_dir, "earthquakes.xml"),
    "gdacs_xml_output_file": os.path.join(_cache_dir, "GDACS_data.xml"),
    "cache_ttl": 600,
}
