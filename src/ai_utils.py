"""
AI utilities for the Global Earthquake Monitor.
Handles Gemini API integration and prompt engineering for seismic data.
"""

import os
import json
import logging
import pandas as pd
import google.generativeai as genai
import streamlit as st

logger = logging.getLogger(__name__)


class SeismicAI:
    def __init__(self):
        self.api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = None

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = self._load_best_model()
        else:
            logger.warning("GOOGLE_API_KEY not found. AI features will be disabled.")

    def is_available(self):
        return self.model is not None

    def _load_best_model(self):
        """Auto-discover and validate the best available Gemini model."""
        preferred_prefixes = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-pro",
        ]
        try:
            available = [
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            # Sort candidates by preferred prefix order
            def sort_key(name):
                for i, prefix in enumerate(preferred_prefixes):
                    if name.startswith(prefix):
                        return i
                return len(preferred_prefixes)

            candidates = sorted(available, key=sort_key)
            for model_name in candidates:
                try:
                    candidate = genai.GenerativeModel(model_name)
                    # Do a real test call — some models appear in list but fail
                    candidate.generate_content("hi")
                    logger.info(f"AI using validated model: {model_name}")
                    return candidate
                except Exception as e:
                    logger.warning(f"Model {model_name} failed validation: {e}")
                    continue
        except Exception as e:
            logger.error(f"list_models failed: {e}")
        logger.error("No working AI model found.")
        return None

    def generate_context_from_df(self, df: pd.DataFrame) -> str:
        """Generate rich, structured context from the earthquake dataframe."""
        if df.empty:
            return "No earthquakes match the current filters."

        df = df.copy()
        df["magnitude"] = pd.to_numeric(df["magnitude"], errors="coerce")
        df["depth_km"] = pd.to_numeric(df["depth_km"], errors="coerce")

        total = len(df)
        avg_mag = df["magnitude"].mean()
        tsunami_count = int((df["tsunami"] == 1).sum()) if "tsunami" in df.columns else 0

        # Alert distribution
        alert_dist = df["alert_level"].value_counts().to_dict()
        # Top countries
        top_countries = df["country"].value_counts().head(15).to_dict()
        # Depth stats
        depth_mean = df["depth_km"].mean()
        # Date range
        date_min = df["date_utc"].min()
        date_max = df["date_utc"].max()

        # Top 10 most significant events
        sig_events = df.nlargest(10, "magnitude")[
            ["place", "magnitude", "alert_level", "country", "depth_km", "main_time"]
        ].to_dict("records")
        sig_text = "\n".join(
            f"  - M{r['magnitude']} at {r['place']} ({r['country']}) | depth {r['depth_km']}km | {r['alert_level']} alert | {r['main_time']}"
            for r in sig_events
        )

        context = (
            f"=== CURRENT DASHBOARD DATA ===\n"
            f"Date range: {date_min} to {date_max}\n"
            f"Total earthquakes: {total}\n"
            f"Average magnitude: {avg_mag:.2f}\n"
            f"Average depth: {depth_mean:.1f} km\n"
            f"Tsunami advisories: {tsunami_count}\n\n"
            f"Alert level breakdown: {json.dumps(alert_dist)}\n"
            f"Top countries by quake count: {json.dumps(top_countries)}\n\n"
            f"Most significant events:\n{sig_text}\n\n"
            f"Available alert_level values (for CHART_FILTER): {list(alert_dist.keys())}\n"
            f"Available countries (for CHART_FILTER): {list(top_countries.keys())}\n"
        )
        return context

    def get_ai_response(self, user_query: str, df_context: str, chat_history: list) -> str:
        if not self.is_available():
            return "⚠️ AI service is not configured. Please provide a GOOGLE_API_KEY."

        system_instruction = f"""You are an expert Seismic Data Analyst AI embedded in the Global Earthquake Monitor dashboard.
Today's date is {pd.Timestamp.now().strftime('%Y-%m-%d')}.

You have deep knowledge of seismology, geology, tectonic plates, USGS/GDACS data, and earthquake science.
You can answer ANY question about earthquakes, their causes, effects, measurements, or the current data.

=== ALERT LEVEL REFERENCE ===
- green: Low impact, minor shaking
- yellow: Potential for damage, moderate shaking
- orange: Significant damage likely, strong shaking
- red: High casualties/damage, major earthquake

=== YOUR CAPABILITIES ===

1. ANSWER questions about the earthquake data using the context provided.

2. GENERATE CHARTS directly in the chat:
   When the user asks for any visualization or chart, ALWAYS generate one.
   The chart uses its OWN filter independent of the dashboard sidebar.
   
   Token format (append at end of response):
   [[CHART: type=scatter|bar|pie|histogram|line, x=col, y=col, color=col, title=Title, filter_alert=green|yellow|orange|red, filter_country=CountryName]]
   
   - filter_alert and filter_country are OPTIONAL. Use them to make the chart show specific subsets.
   - For COUNT charts (quakes per country/alert): use y=count
   - For histograms: specify only x (no y needed)
   
   Available columns: magnitude, depth_km, alert_level, country, date_utc, tsunami, sig, felt
   
   Examples:
   [[CHART: type=bar, x=country, y=count, title=Earthquakes by Country]]
   [[CHART: type=scatter, x=depth_km, y=magnitude, color=alert_level, title=Depth vs Magnitude]]
   [[CHART: type=histogram, x=magnitude, title=Magnitude Distribution]]
   [[CHART: type=bar, x=country, y=count, filter_alert=green, title=Green Alert Quakes by Country]]
   [[CHART: type=scatter, x=depth_km, y=magnitude, filter_country=Indonesia, title=Indonesia: Depth vs Mag]]
   [[CHART: type=pie, x=alert_level, y=count, title=Alert Level Breakdown]]

3. NAVIGATE to dashboard tabs (only if user explicitly asks to go somewhere):
   [[NAVIGATE: Overview|Distribution|Geographic|Time Series]]

4. CHANGE DATE RANGE (only if user explicitly asks):
   [[SET_DATE: YYYY-MM-DD, YYYY-MM-DD]]

5. CHANGE DASHBOARD FILTERS (only if user explicitly wants the whole dashboard filtered):
   [[SET_SOURCE: USGS|GDACS|Both]]
   [[SET_ALERT: green, yellow]]  (Changes sidebar for whole dashboard)
   [[SET_COUNTRY: Indonesia, Chile]]  (Changes sidebar for whole dashboard)

=== IMPORTANT RULES ===
- When a user asks to "show me a chart of X" or "visualize X" - ALWAYS use CHART token, do NOT navigate.
- When a user asks to "show me X with green alert" in a chart context - use filter_alert in CHART token, do NOT use SET_ALERT.
- Only use SET_ALERT / SET_COUNTRY when the user says something like "filter the dashboard" or "change the sidebar".
- Do NOT add [[NAVIGATE]] when generating a chart - the chart appears in the chat itself.
- Be extremely helpful, concise, and knowledgeable. Use your seismology expertise freely.
- If asked what you can do, list all your chart types, filter capabilities, and knowledge domains.
"""

        full_prompt = f"{system_instruction}\n\n{df_context}\n\nUser Question: {user_query}"

        try:
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"❌ Sorry, I encountered an error: {str(e)}"
