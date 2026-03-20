"""PDF Situation Report generator for the Global Earthquake Monitor."""

import io
import logging
import math
import time
from datetime import datetime
from typing import Any

import pandas as pd
from fpdf import FPDF

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_PAGE_W = 210  # A4 width in mm
_MARGIN = 15
_CONTENT_W = _PAGE_W - 2 * _MARGIN

_ALERT_COLORS_RGB: dict[str, tuple[int, int, int]] = {
    "Red": (239, 68, 68),
    "Orange": (249, 115, 22),
    "Yellow": (245, 158, 11),
    "Green": (34, 197, 94),
    "Unknown": (107, 114, 128),
}

# A pleasant categorical palette for histogram bars
_BAR_PALETTE: list[tuple[int, int, int]] = [
    (59, 130, 246),   # blue
    (16, 185, 129),   # emerald
    (245, 158, 11),   # amber
    (239, 68, 68),    # red
    (139, 92, 246),   # violet
    (6, 182, 212),    # cyan
]


# ── Native chart helpers ──────────────────────────────────────────────────────
def _draw_magnitude_histogram(
    pdf: FPDF, df: pd.DataFrame, x: float, y: float, w: float, h: float
) -> None:
    """Draw a simple magnitude histogram natively in FPDF."""
    t0 = time.time()
    mags = pd.to_numeric(df["magnitude"], errors="coerce").dropna()
    if mags.empty:
        return

    # Create bins
    bin_edges = [i * 0.5 for i in range(0, 21)]  # 0.0 to 10.0 in 0.5 steps
    counts, _ = pd.cut(mags, bins=bin_edges, retbins=True)
    hist = counts.value_counts().sort_index()

    # Title
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(w, 6, "Magnitude Distribution", align="C")

    chart_y = y + 8
    chart_h = h - 14
    max_count = max(hist.values) if len(hist) > 0 else 1
    if max_count == 0:
        max_count = 1
    n_bars = len(hist)
    if n_bars == 0:
        return
    bar_w = w / n_bars

    for i, (interval, count) in enumerate(hist.items()):
        bar_h = (count / max_count) * chart_h
        bx = x + i * bar_w
        by = chart_y + chart_h - bar_h
        color = _BAR_PALETTE[i % len(_BAR_PALETTE)]
        pdf.set_fill_color(*color)
        if bar_h > 0:
            pdf.rect(bx + 0.5, by, bar_w - 1, bar_h, style="F")

    # X-axis label
    pdf.set_xy(x, chart_y + chart_h + 1)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(w, 4, "Magnitude", align="C")
    logger.info("[PDF] Drew magnitude histogram in %.3fs", time.time() - t0)


def _draw_alert_pie(
    pdf: FPDF, df: pd.DataFrame, x: float, y: float, w: float, h: float
) -> None:
    """Draw a simple alert-level pie chart natively in FPDF."""
    t0 = time.time()
    counts = df["alert_level"].value_counts()
    if counts.empty:
        return

    # Title
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(w, 6, "Alert Level Breakdown", align="C")

    total = counts.sum()
    cx = x + w / 2
    cy = y + 8 + (h - 20) / 2
    radius = min(w, h - 20) / 2 - 4

    # Draw pie slices as colored arcs approximated by filled triangles
    start_angle = 0.0
    for level, count in counts.items():
        sweep = (count / total) * 360.0
        color = _ALERT_COLORS_RGB.get(str(level), (107, 114, 128))
        pdf.set_fill_color(*color)

        # Draw the slice as a polygon (fan of small triangles)
        n_steps = max(int(sweep / 3), 2)
        points = [(cx, cy)]
        for step in range(n_steps + 1):
            angle_rad = math.radians(start_angle + sweep * step / n_steps)
            px = cx + radius * math.cos(angle_rad)
            py = cy + radius * math.sin(angle_rad)
            points.append((px, py))

        # Use FPDF polygon if available, otherwise draw triangle fan
        if hasattr(pdf, "polygon"):
            pdf.polygon(points, style="F")
        else:
            for j in range(1, len(points) - 1):
                x1, y1 = points[0]
                x2, y2 = points[j]
                x3, y3 = points[j + 1]
                pdf.set_xy(x1, y1)
                # Approximate with a filled triangle
                _draw_triangle(pdf, x1, y1, x2, y2, x3, y3, color)

        start_angle += sweep

    # Legend
    legend_y = y + 8 + (h - 20) + 2
    pdf.set_font("Helvetica", "", 7)
    legend_x = x
    for level, count in counts.items():
        color = _ALERT_COLORS_RGB.get(str(level), (107, 114, 128))
        pdf.set_fill_color(*color)
        pdf.rect(legend_x, legend_y, 3, 3, style="F")
        pdf.set_xy(legend_x + 4, legend_y - 0.5)
        pdf.set_text_color(51, 65, 85)
        label = f"{level} ({count})"
        pdf.cell(20, 4, label, align="L")
        legend_x += 24

    logger.info("[PDF] Drew alert pie chart in %.3fs", time.time() - t0)


def _draw_triangle(
    pdf: FPDF,
    x1: float, y1: float,
    x2: float, y2: float,
    x3: float, y3: float,
    color: tuple[int, int, int],
) -> None:
    """Draw a filled triangle (fallback for older FPDF without polygon)."""
    pdf.set_fill_color(*color)
    if hasattr(pdf, "polygon"):
        pdf.polygon([(x1, y1), (x2, y2), (x3, y3)], style="F")


# ── Top events helper ─────────────────────────────────────────────────────────
def _get_top_events(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Return the top_n events sorted by magnitude descending."""
    cols = ["place", "magnitude", "depth_km", "main_time"]
    available = [c for c in cols if c in df.columns]
    events = df[available].copy()
    events["magnitude"] = pd.to_numeric(events["magnitude"], errors="coerce")
    if "depth_km" in events.columns:
        events["depth_km"] = pd.to_numeric(events["depth_km"], errors="coerce")
    events = (
        events.dropna(subset=["magnitude"])
        .sort_values("magnitude", ascending=False)
        .head(top_n)
    )
    return events


# ── Main generator ────────────────────────────────────────────────────────────
def generate_situation_report(
    df: pd.DataFrame,
    filters: dict[str, Any],
    generated_at: datetime,
) -> bytes:
    """Generate a professional PDF situation report and return raw bytes.

    Args:
        df: The filtered earthquake DataFrame currently displayed.
        filters: Dict with keys: source, start_date, end_date, min_mag,
                 alerts (list), countries (list).
        generated_at: UTC timestamp of report generation.

    Returns:
        Raw PDF bytes suitable for Streamlit download_button.
    """
    t_total = time.time()
    logger.info("[PDF] === Starting PDF generation (%d rows) ===", len(df))

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=_MARGIN)
    pdf.add_page()
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)

    # ── Header ────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(30, 58, 138)  # indigo-900
    pdf.cell(0, 12, "Global Earthquake Monitor", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(71, 85, 105)  # slate-500
    pdf.cell(0, 8, "Situation Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(
        0,
        6,
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    # Divider line
    pdf.set_draw_color(203, 213, 225)
    pdf.line(_MARGIN, pdf.get_y(), _PAGE_W - _MARGIN, pdf.get_y())
    pdf.ln(6)

    logger.info("[PDF] Header done in %.3fs", time.time() - t_total)

    # ── Filter Summary ────────────────────────────────────────────────────
    t_section = time.time()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Active Filters", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(51, 65, 85)

    source = filters.get("source", "N/A")
    start = filters.get("start_date", "N/A")
    end = filters.get("end_date", "N/A")
    min_mag = filters.get("min_mag", "N/A")

    pdf.cell(0, 6, f"Source: {source}    |    Date Range: {start} to {end}    |    Min Magnitude: {min_mag}", new_x="LMARGIN", new_y="NEXT")

    alerts = filters.get("alerts", [])
    countries = filters.get("countries", [])
    if alerts:
        alert_str = ", ".join(str(a) for a in alerts[:10])
        if len(alerts) > 10:
            alert_str += f" ... (+{len(alerts) - 10} more)"
        pdf.cell(0, 6, f"Alert Levels: {alert_str}", new_x="LMARGIN", new_y="NEXT")
    if countries:
        country_str = ", ".join(str(c) for c in countries[:10])
        if len(countries) > 10:
            country_str += f" ... (+{len(countries) - 10} more)"
        pdf.cell(0, 6, f"Countries: {country_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    logger.info("[PDF] Filter summary done in %.3fs", time.time() - t_section)

    # ── KPI Section ───────────────────────────────────────────────────────
    t_section = time.time()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Key Performance Indicators", new_x="LMARGIN", new_y="NEXT")

    mags = pd.to_numeric(df["magnitude"], errors="coerce")
    total_quakes = len(df)
    avg_mag = float(mags.mean()) if not mags.dropna().empty else 0.0
    max_mag_val = float(mags.max()) if not mags.dropna().empty else 0.0
    tsunami_count = (
        int((df["tsunami"] == 1).sum()) if "tsunami" in df.columns else 0
    )

    # Draw KPI boxes
    box_w = _CONTENT_W / 4
    box_h = 18
    kpi_y = pdf.get_y()
    kpis = [
        ("Total Quakes", str(total_quakes)),
        ("Avg Magnitude", f"{avg_mag:.1f}"),
        ("Max Magnitude", f"{max_mag_val:.1f}"),
        ("Tsunami Alerts", str(tsunami_count)),
    ]
    for i, (label, value) in enumerate(kpis):
        bx = _MARGIN + i * box_w
        # Box background
        pdf.set_fill_color(241, 245, 249)  # slate-100
        pdf.rect(bx, kpi_y, box_w - 2, box_h, style="F")
        # Value
        pdf.set_xy(bx, kpi_y + 2)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(box_w - 2, 8, value, align="C")
        # Label
        pdf.set_xy(bx, kpi_y + 10)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(box_w - 2, 6, label, align="C")

    pdf.set_y(kpi_y + box_h + 6)

    logger.info("[PDF] KPI section done in %.3fs", time.time() - t_section)

    # ── Charts (native FPDF — no Kaleido/Chromium) ────────────────────────
    t_section = time.time()
    if not df.empty:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, "Visualizations", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        chart_w = _CONTENT_W / 2 - 2
        chart_h = 55
        chart_y = pdf.get_y()

        _draw_magnitude_histogram(pdf, df, _MARGIN, chart_y, chart_w, chart_h)
        _draw_alert_pie(pdf, df, _MARGIN + chart_w + 4, chart_y, chart_w, chart_h)

        pdf.set_y(chart_y + chart_h + 6)

    logger.info("[PDF] Charts section done in %.3fs", time.time() - t_section)

    # ── Top Events Table ──────────────────────────────────────────────────
    t_section = time.time()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, "Top 10 Significant Events", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    events = _get_top_events(df, top_n=10)

    if events.empty:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 8, "No significant events for current filters.", new_x="LMARGIN", new_y="NEXT")
    else:
        # Table header
        col_widths = [70, 25, 25, 60]
        headers = ["Place", "Mag", "Depth (km)", "Time (UTC)"]
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        for header, cw in zip(headers, col_widths):
            pdf.cell(cw, 7, header, border=1, fill=True, align="C")
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(51, 65, 85)
        for idx, (_, row) in enumerate(events.iterrows()):
            if idx % 2 == 0:
                pdf.set_fill_color(248, 250, 252)
            else:
                pdf.set_fill_color(255, 255, 255)

            place = str(row.get("place", "Unknown"))[:35]
            mag = f"{row['magnitude']:.1f}" if pd.notna(row.get("magnitude")) else "N/A"
            depth = (
                f"{row['depth_km']:.1f}"
                if "depth_km" in row.index and pd.notna(row.get("depth_km"))
                else "N/A"
            )
            time_str = ""
            if "main_time" in row.index and row.get("main_time"):
                try:
                    t = pd.to_datetime(row["main_time"], utc=True)
                    time_str = t.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = str(row["main_time"])[:20]

            pdf.cell(col_widths[0], 7, place, border=1, fill=True)
            pdf.cell(col_widths[1], 7, mag, border=1, fill=True, align="C")
            pdf.cell(col_widths[2], 7, depth, border=1, fill=True, align="C")
            pdf.cell(col_widths[3], 7, time_str, border=1, fill=True, align="C")
            pdf.ln()

    logger.info("[PDF] Events table done in %.3fs", time.time() - t_section)

    # ── Footer ────────────────────────────────────────────────────────────
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(
        0,
        5,
        "This report was auto-generated by the Global Earthquake Monitor dashboard.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(0, 5, "Data sources: USGS & GDACS. For informational purposes only.")

    # Return bytes
    t_section = time.time()
    buf = io.BytesIO()
    pdf.output(buf)
    pdf_bytes = buf.getvalue()
    logger.info("[PDF] Serialization done in %.3fs (%d bytes)", time.time() - t_section, len(pdf_bytes))
    logger.info("[PDF] === Total PDF generation: %.3fs ===", time.time() - t_total)
    return pdf_bytes
