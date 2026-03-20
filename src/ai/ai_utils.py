import os
import re
import pandas as pd
import google.generativeai as genai
import logging
import streamlit as st
from typing import List, Dict

logger = logging.getLogger(__name__)


# List of models to try in order of preference (most are per-model quota)
MODEL_POOL = [
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-001",
    "gemini-flash-lite-latest",
]


class SeismicAI:
    def __init__(self) -> None:
        """Initialize the AI engine with API keys from secrets or environment."""
        # Prefer st.secrets, fallback to os.getenv
        self.api_key: str | None = None
        try:
            self.api_key = st.secrets.get("GOOGLE_API_KEY")
        except Exception:
            pass

        if not self.api_key:
            self.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            logger.error("GOOGLE_API_KEY not found in environment.")

        if self.api_key:
            genai.configure(api_key=self.api_key)

        self.last_error_type = None

    def is_available(self) -> bool:
        """Check if the AI service is configured and reachable."""
        return self.api_key is not None

    def generate_context_from_df(self, df: pd.DataFrame) -> str:
        """Generate a summarized textual context for the AI from the dashboard data."""
        if df.empty:
            return "No earthquakes match the current filters."

        total = len(df)
        mags = pd.to_numeric(df["magnitude"], errors="coerce").dropna()
        avg_mag = float(mags.mean()) if not mags.empty else 0.0
        tsunami_count = (
            int((df["tsunami"] == 1).sum()) if "tsunami" in df.columns else 0
        )

        # Sort by magnitude for the top recent events
        latest = df.sort_values("magnitude", ascending=False).head(5)

        context = f"Total earthquakes: {total}\n"
        context += f"Average magnitude: {avg_mag:.2f}\n"
        context += f"Tsunami advisories: {tsunami_count}\n"
        context += "Latest significant events:\n"
        for _, row in latest.iterrows():
            country = row.get("country", "Unknown")
            context += f"- {row['place']} ({country}): Magnitude {row['magnitude']} at {row['main_time']}\n"
            if row.get("alert_level"):
                context += f"  (Alert: {row['alert_level']})\n"
        return context

    def get_ai_response(
        self, user_query: str, context: str, history: List[Dict[str, str]]
    ) -> str:
        """Fetch a conversational response from Gemini with automatic model fallback."""
        if not self.is_available():
            return "I'm sorry, the AI service is not configured (missing API key)."

        prompt = f"""
        You are a seismic activity expert. Use the following context and chat history to answer the user query.
        
        CONTEXT:
        {context}
        
        CAPABILITIES:
        - [[NAVIGATE: TabName]] to switch tabs (Overview, Distribution, Geographic, Time Series, AI Assistant).
        - [[SET_DATE: YYYY-MM-DD, YYYY-MM-DD]] to change date range.
        - [[SET_SOURCE: USGS|GDACS|Both]] to change source.
        - [[SET_ALERT: green|yellow|orange|red]] to filter by alert (comma separated).
        - [[SET_COUNTRY: CountryName]] to filter (comma separated).
        - [[CHART: type=scatter|bar|pie|histogram|line|box, title=..., x=..., y=..., color=..., filter_alert=..., filter_country=...]]
        
        USER QUERY: {user_query}
        """

        # Try models in the pool until one succeeds
        last_exception = None
        for model_name in MODEL_POOL:
            try:
                model = genai.GenerativeModel(model_name)

                if not history:
                    response = model.generate_content(prompt)
                    text = str(response.text)
                else:
                    gemini_history = []
                    for m in history:
                        role = "user" if m["role"] == "user" else "model"
                        gemini_history.append({"role": role, "parts": [m["content"]]})

                    chat = model.start_chat(history=gemini_history)
                    response = chat.send_message(prompt)
                    text = str(response.text)

                # Success! Log if we recovered
                if self.last_error_type == "429":
                    logger.info("AI Quota Restored with model %s", model_name)
                self.last_error_type = None
                return text

            except Exception as e:
                last_exception = e
                err_str = str(e)
                # If it's a 429 or 404, we try the next model
                if "429" in err_str or "quota" in err_str.lower() or "404" in err_str:
                    logger.warning(
                        "Switching model: %s failed with %s. Trying next...",
                        model_name,
                        err_str,
                    )
                    self.last_error_type = "429" if "429" in err_str else "404"
                    continue
                else:
                    # For other errors (like invalid key), we stop immediately
                    logger.error("AI Error (Permanent): %s", e)
                    break

        # If we get here, all models failed
        err_str = str(last_exception)
        if "429" in err_str or "quota" in err_str.lower():
            # Try to extract "retry in X.Xs" from the error message for the user
            wait_time = "a moment"
            match = re.search(r"retry in ([\d\.]+)s", err_str)
            if match:
                wait_time = f"{float(match.group(1)):.1f} seconds"
            return f"💨 All AI models are currently exhausted. Please try again in {wait_time}!"

        return "I'm sorry, I'm having trouble connecting to my seismic brain right now."
