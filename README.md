# Global Earthquake Monitor — Live Dashboard

A real-time **data science dashboard** built with **Streamlit** that monitors global earthquake activity using the **USGS Earthquake Catalog API**.

The application fetches earthquake data with user-selectable date ranges (including historical data going back years), exports raw **QuakeML XML** for XSLT transformation, and presents interactive visualizations with filtering capabilities.

---

## 🔗 Live Demo

👉 **[https://global-earthquake-monitor.streamlit.app](https://global-earthquake-monitor.streamlit.app)**

---

## 📸 Dashboard Preview

![Dashboard Screenshot](assets/dashboard_screenshot.png)

*Interactive dashboard showing daily earthquake trends, magnitude distributions, alert level breakdowns, depth analysis, and geographic mapping.*

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NadimBaboun/Global-Disaster-Live-Monitor.git
   cd Global-Disaster-Live-Monitor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser** to `http://localhost:8501`

---

## 📊 Key Features

### Data Pipeline
- **USGS Earthquake Catalog API** — reliable, free, no API key required
- **Historical data access** — select any date range (days, months, or years back)
- **Dual-format fetch** — GeoJSON for dashboard, QuakeML XML for export
- **Network resilience** — automatic fallback to cached CSV on fetch failures

### XML Export for XSLT
- Raw **QuakeML XML** saved to `earthquakes.xml` on every fetch
- **📥 Download XML** button in the sidebar for one-click export
- Standard XML format ideal for XSLT transformation into custom presentations

### Data Processing
- GeoJSON parsing with automatic field extraction
- Magnitude-based alert level classification (🔴 ≥7.0, 🟠 ≥5.5, 🟢 ≥4.0)
- Country/region extraction from USGS place strings
- USGS significance score mapping for severity ranking

### Interactive Dashboard
- **Date range picker** — drives the API query for historical or recent data
- **Magnitude slider** — filter earthquakes by minimum magnitude (1.0–8.0)
- **Multi-filter system** — alert level, country/region
- **KPI sidebar** — earthquake count, average/max magnitude
- **10+ chart types** — line, bar, pie, histogram, boxplot, scatter, stacked bar, geographic map
- **Dark-themed UI** — custom matplotlib styling for readability

---

## 🗂️ Project Structure

```
📁 Global-Disaster-Live-Monitor/
├── assets/               # Screenshots and media
├── app.py                # Streamlit UI (filters, charts, layout)
├── data.py               # Data layer (USGS fetch, parse, cache, XML export)
├── chart_utils.py        # Dark-themed chart helpers
├── earthquakes.xml       # Auto-generated QuakeML XML (for XSLT transformation)
├── requirements.txt      # Python dependencies
├── .gitignore            # Excluded files (cache, bytecode, etc.)
└── README.md
```

### Code Organization

| File | Responsibility | Key Functions |
|---|---|---|
| **`data.py`** | USGS API fetching & caching | `fetch_usgs_geojson()`, `fetch_usgs_xml()`, `geojson_to_df()`, `load_data_with_cache()` |
| **`chart_utils.py`** | Chart styling | `dark_chart()` context manager, `darken_fig()` |
| **`app.py`** | UI layout & filters | Date range picker, magnitude slider, chart rendering, XML download |

---

## 🌐 Data Source

**USGS Earthquake Hazards Program — Earthquake Catalog API**  
📍 [https://earthquake.usgs.gov/fdsnws/event/1/](https://earthquake.usgs.gov/fdsnws/event/1/)

The API provides comprehensive earthquake data including:
- 🌍 **Magnitude & type** (Mw, Mb, Ml, etc.)
- 📏 **Depth** (km below surface)
- 📍 **Precise location** (latitude, longitude, place name)
- 🌊 **Tsunami flag** — whether a tsunami advisory was issued
- 👥 **Felt reports** — number of people who reported feeling the earthquake
- 📊 **Significance score** — composite severity metric (0–1000+)

Output formats: **QuakeML (XML)**, GeoJSON, CSV, KML, Text

---

## 🛠️ Technical Highlights

### Error Handling
- **Specific exception catching**: `requests.RequestException`, `ValueError`, `KeyError`
- **Logging integration**: Failed fetches are logged for debugging on Streamlit Cloud
- **Cache write isolation**: Disk errors don't prevent showing fresh data
- **XML fetch isolation**: XML export failure doesn't block dashboard rendering

### Performance
- **Streamlit caching**: `@st.cache_data(ttl=600)` for API fetches
- **Pre-computed aggregates**: Daily counts/magnitudes computed once and reused
- **Efficient filtering**: Single boolean mask for all sidebar selections

### Code Quality
- **Separation of concerns**: Data layer, UI layer, chart utilities in separate modules
- **Comprehensive docstrings**: All public functions documented
- **Inline comments**: Explain *why*, not *what*

---

## 📈 Data Science Concepts Demonstrated

- **Data ingestion** from external APIs (REST/JSON + XML)
- **XML export** for XSLT transformation pipelines
- **Data cleaning** and type conversion (epoch timestamps, numeric coercion)
- **Feature engineering** (alert level derivation from magnitude, country extraction from place strings)
- **Time-series analysis** (daily aggregates, rolling averages, cumulative sums)
- **Exploratory data analysis** (distributions, depth vs magnitude scatter, geographic patterns)
- **Interactive visualization** (filters, multi-chart dashboards, map rendering)

---

## 📝 License

This project is for educational and portfolio purposes.

---

## 🙋 Author

**Nadim Baboun**  
🔗 [GitHub Profile](https://github.com/NadimBaboun)