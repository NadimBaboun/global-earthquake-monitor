# Global Disaster Monitor (GDACS)

This project is an interactive **data science dashboard** built with **Streamlit** that monitors global natural disaster alerts using the **GDACS (Global Disaster Alert and Coordination System)** RSS feed.

The application fetches near real-time disaster data, cleans and structures the raw XML feed, performs aggregation and analysis, and presents the results through interactive charts, tables, and a map-based visualization.

---

## Live Demo
👉 https://global-disaster-live-monitor.streamlit.app

---

## Data Source
- **GDACS RSS Feed**: https://www.gdacs.org/xml/rss.xml  
GDACS provides real-time alerts for natural disasters such as earthquakes, floods, cyclones, wildfires, and volcanic activity worldwide.

---

## Key Features

- **Live Data Ingestion**
  - Fetches XML data from the GDACS RSS feed
  - Handles network issues and invalid responses gracefully
  - Falls back to cached data if live fetch fails

- **Data Processing & Feature Engineering**
  - Parses XML using namespaces
  - Converts timestamps to timezone-aware datetime objects
  - Creates a unified event time (`main_time`) for analysis
  - Extracts and cleans numerical and categorical fields

- **Interactive Filtering**
  - Filter alerts by:
    - Event type
    - Alert level
    - Country
    - Date range
  - Smart default selections for improved usability

- **Data Analysis**
  - Daily alert counts
  - Daily average alert score
  - Cumulative alert trends
  - Distribution of alert levels and event types
  - Top affected countries

- **Visualization**
  - Time-series line charts
  - Bar charts and pie charts
  - Interactive geographic map showing high-severity alerts
  - Tabular view of recent disaster events

---

## Data Science Concepts Demonstrated

- Data ingestion from external APIs
- XML parsing and data normalization
- Feature engineering
- Time-series aggregation
- Exploratory data analysis (EDA)
- Data visualization
- Basic UX design for analytical dashboards
