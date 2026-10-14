"""Offline checks for response parsing and request failure handling."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from src.weather import WeatherAPIError, forecast_frame, geocode, request_json

FIXTURES = Path(__file__).parent / "fixtures"


class WeatherTests(unittest.TestCase):
    def test_forecast_fields_and_weather_codes(self) -> None:
        payload = json.loads((FIXTURES / "weather_forecast.json").read_text(encoding="utf-8"))
        frame = forecast_frame(payload)
        self.assertEqual(len(frame), 3)
        self.assertEqual(frame.loc[0, "weather"], "Slight rain showers")
        self.assertEqual(frame.loc[1, "max_temp_c"], 16.6)

    def test_no_geocoding_results_is_empty_list(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {}
        session.get.return_value = response
        self.assertEqual(geocode("Nowhere", session=session), [])

    def test_invalid_daily_arrays_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            forecast_frame({"daily": {"time": ["today"], "temperature_2m_max": [], "temperature_2m_min": [1], "precipitation_sum": [0], "wind_speed_10m_max": [0], "weather_code": [0]}})

    def test_retries_server_error_and_returns_json(self) -> None:
        session = Mock()
        failed = Mock(status_code=503)
        failed.raise_for_status.side_effect = requests.HTTPError(response=failed)
        succeeded = Mock()
        succeeded.json.return_value = {"ok": True}
        session.get.side_effect = [failed, succeeded]
        self.assertEqual(request_json(session, "https://example.test", retries=1, backoff=0), {"ok": True})
        self.assertEqual(session.get.call_count, 2)

    def test_connection_failure_has_clear_custom_error(self) -> None:
        session = Mock()
        session.get.side_effect = requests.ConnectionError("offline")
        with self.assertRaisesRegex(WeatherAPIError, "Weather request failed"):
            request_json(session, "https://example.test", retries=0, backoff=0)


if __name__ == "__main__":
    unittest.main()
