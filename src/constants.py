"""Shared UI constants used across dashboard modules."""

from typing import Final

# Hex palette for matplotlib/HTML usage
ALERT_HEX_COLORS: Final[dict[str, str]] = {
    "Red": "#ef4444",
    "Orange": "#f97316",
    "Yellow": "#f59e0b",
    "Green": "#22c55e",
    "Unknown": "#6b7280",
}

# RGBA palette for map markers (pydeck)
ALERT_RGBA_COLORS: Final[dict[str, list[int]]] = {
    "Red": [239, 68, 68, 180],
    "Orange": [249, 115, 22, 180],
    "Yellow": [234, 179, 8, 180],
    "Green": [34, 197, 94, 180],
    "Unknown": [107, 114, 128, 150],
}

DEFAULT_ALERT_HEX: Final[str] = ALERT_HEX_COLORS["Unknown"]
DEFAULT_ALERT_RGBA: Final[list[int]] = ALERT_RGBA_COLORS["Unknown"]

# General categorical palette for Plotly charts (based on the dashboard's blue theme)
PLOTLY_THEME_COLORS: Final[list[str]] = [
    "#3b82f6",  # Blue 500
    "#10b981",  # Emerald 500
    "#f59e0b",  # Amber 500
    "#ef4444",  # Red 500
    "#8b5cf6",  # Violet 500
    "#06b6d4",  # Cyan 500
    "#f472b6",  # Pink 400
]

PLOTLY_FONT: Final[str] = "Inter, sans-serif"
