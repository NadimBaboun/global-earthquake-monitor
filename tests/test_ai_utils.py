import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai import ai_utils


@pytest.fixture
def mock_genai():
    with (
        patch("google.generativeai.configure") as mock_conf,
        patch("google.generativeai.GenerativeModel") as mock_model,
        patch("google.generativeai.list_models") as mock_list,
    ):
        # Mock available models
        mock_m1 = MagicMock()
        mock_m1.name = "models/gemini-pro"
        mock_m1.supported_generation_methods = ["generateContent"]
        mock_list.return_value = [mock_m1]

        # Mock instance
        instance = mock_model.return_value
        instance.generate_content.return_value.text = "Hello from AI"

        yield {
            "configure": mock_conf,
            "model": mock_model,
            "list_models": mock_list,
            "instance": instance,
        }


@pytest.fixture
def mock_st_secrets():
    with patch("streamlit.secrets") as mock_secrets:
        mock_secrets.get.return_value = "fake-key"
        yield mock_secrets


def test_seismic_ai_init(mock_genai, mock_st_secrets):
    ai = ai_utils.SeismicAI()
    assert ai.api_key == "fake-key"
    assert ai.is_available() is True
    mock_genai["configure"].assert_called_with(api_key="fake-key")


def test_generate_context_empty_df():
    ai = MagicMock(spec=ai_utils.SeismicAI)
    # Actually use the real method but on a mock object to avoid __init__
    context = ai_utils.SeismicAI.generate_context_from_df(ai, pd.DataFrame())
    assert "No earthquakes match" in context


def test_generate_context_with_data():
    df = pd.DataFrame(
        {
            "magnitude": [5.0, 6.0],
            "depth_km": [10, 20],
            "tsunami": [1, 0],
            "alert_level": ["Orange", "Green"],
            "country": ["Japan", "USA"],
            "date_utc": [pd.Timestamp("2024-01-01").date()] * 2,
            "place": ["Tokyo", "SF"],
            "main_time": [pd.Timestamp("2024-01-01")] * 2,
        }
    )
    ai = MagicMock(spec=ai_utils.SeismicAI)
    context = ai_utils.SeismicAI.generate_context_from_df(ai, df)

    assert "Total earthquakes: 2" in context
    assert "Average magnitude: 5.50" in context
    assert "Tsunami advisories: 1" in context
    assert "Japan" in context
    assert "Orange" in context


def test_get_ai_response_success(mock_genai, mock_st_secrets):
    ai = ai_utils.SeismicAI()
    response = ai.get_ai_response("What happened?", "Context here", [])
    assert response == "Hello from AI"
    mock_genai["instance"].generate_content.assert_called()


def test_get_ai_response_not_available():
    with patch("streamlit.secrets") as mock_secrets:
        mock_secrets.get.return_value = None
        with patch.dict("os.environ", {}, clear=True):
            ai = ai_utils.SeismicAI()
            assert ai.is_available() is False
            response = ai.get_ai_response("Hi", "Context", [])
            assert "AI service is not configured" in response
