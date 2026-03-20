A high-performance, real-time **data science dashboard** built with **Streamlit** that monitors global earthquake activity by aggregating and normalizing data from multiple sources: **USGS Earthquake Catalog** and **GDACS (Global Disaster Alert and Coordination System)**.

The application uses a **strategy-based provider architecture** to fetch data in parallel, ensures long-term persistence with a **local cache**, and presents interactive, theme-consistent visualizations powered by **Plotly**.

---

## 🔗 Live Demo

👉 **[https://global-earthquake-live-monitor.streamlit.app](https://global-earthquake-live-monitor.streamlit.app)**

---

## 📸 Dashboard Preview

![Dashboard Screenshot](assets/dashboard_screenshot.png)

*Interactive dashboard showing daily earthquake trends, magnitude distributions, alert level breakdowns, depth analysis, and geographic mapping.*

---

## 🚀 Quick Start (Recommended: Docker)

Testing and deploying the application is easiest using **Docker**:

1. **Clone and Build**
   ```bash
   git clone https://github.com/NadimBaboun/global-earthquake-monitor.git
   cd global-earthquake-monitor
   docker-compose up --build
   ```

2. **Access the Dashboard** at `http://localhost:8501`

### Or Run Locally with Python

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**
   ```bash
   streamlit run src/app.py
   ```

---

## 📊 Key Features

### 📡 Multi-Provider Data Pipeline
- **Parallel Fetching** — Uses `ThreadPoolExecutor` to fetch data from **USGS** and **GDACS** simultaneously, significantly reducing load times.
- **Provider Architecture** — Modular design (Strategy Pattern) for data providers, making it easy to add new seismic sources.
- **Historical data access** — Select any date range (days, months, or years back).
- **Network Resilience** — Automatic fallback to a persistent **local `.cache/` directory** if upstream APIs are unreachable.

### 📥 XML Export for XSLT
- Raw **QuakeML XML** and GDACS XML files are exported on every fetch.
- **Download XML** buttons in the sidebar for one-click export, ideal for downstream XSLT transformation pipelines.

### 🧩 Data Science & Processing
- **Schema Normalization** — Consistent data schema across differing providers (GeoJSON vs RSS/XML).
- **Alert Classification** — Standardized alert level logic (🔴 ≥7.0, 🟠 ≥5.5, 🟡 ≥4.5).
- **Region Extraction** — Automated parsing of country and region tags from unstructured location strings.
- **Tsunami Flags** — Integrated warnings and specialized map styling for tsunami-prone events.

### 📈 Interactive Dashboard
- **Plotly Visualizations** — 100% interactive charts (Bar, Pie, Boxplot, Scatter, Line) with custom hover tooltips and consistent dark-theme styling.
- **Dynamic Map (Pydeck)** — High-performance scatterplot map with radius scaling and alert-level color coding.
- **Real-time Filters** — Instantly filter by date, magnitude, region, and alert level.

---

## 🗂️ Project Structure

```text
📁 global-earthquake-monitor/
├── src/                  # Python source code
│   ├── providers/        # [NEW] Data provider implementations (USGS, GDACS)
│   ├── app.py            # Streamlit UI Entry Point
│   ├── components.py     # [NEW] Reusable UI components (CSS, Tables)
│   ├── data.py           # Core data orchestrator (Parallel fetching, Cache)
│   ├── data_utils.py     # Schema mapping & cleaning
│   ├── map_utils.py      # Pydeck mapping & styling
│   └── chart_utils.py    # Plotly theme & template configuration
├── tests/                # [NEW] Pytest suite covering GDACS, Map Utils, and Core Data
├── docs/                 # Documentation & architectural diagrams
├── xml/                  # XSLT transformation files
├── .cache/               # Local persistent cache (ignored by git)
├── Dockerfile            # [NEW] Container configuration
├── docker-compose.yml    # [NEW] Orchestration & Volume setup
├── requirements.txt      # Project dependencies
└── README.md
```

---

## 🌐 Data Sources

1. **USGS Earthquake Catalog** — [fdsnws/event/1/](https://earthquake.usgs.gov/fdsnws/event/1/) (GeoJSON/QuakeML)
2. **GDACS RSS Feed** — [Global Disaster Alert System](https://www.gdacs.org/) (RSS/XML)

---

## 🛠️ Technical Highlights

### Performance & Scalability
- **Multithreading**: Parallelizing API requests for a more responsive user experience.
- **Dockerization**: Consistent development environment using `python:3.11-slim`.
- **Streamlit Caching**: Optimized `@st.cache_data` decorators to minimize redundant processing.

### Quality Assurance
- **Linting**: Enforced code quality with `ruff`.
- **Testing**: Comprehensive `pytest` suite for core utilities and data parsers.
- **Persistence**: Decoupled cache from system temp to ensure network resilience across reboots.

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

This project is licensed. See the `LICENSE` file for details.

Unless stated otherwise by the author, all rights are reserved.
If you want to reuse or redistribute any part of this repository, please
contact the author first for permission.

---

## 🙋 Author

**Nadim Baboun**  
🔗 [GitHub Profile](https://github.com/nadeemtsf)
