"""Direct, low-volume clients for the approved Open-Meteo and MET APIs."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MET_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


class WeatherAPIError(RuntimeError):
    """Raised when an API request or response fails."""


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10,
    retries: int = 2,
    backoff: float = 0.5,
) -> dict[str, Any]:
    """GET JSON with a timeout, status checks, and capped exponential retry."""
    response = request_response(
        session,
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=retries,
        backoff=backoff,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise WeatherAPIError("API response must be a JSON object")
    return payload


def request_response(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10,
    retries: int = 2,
    backoff: float = 0.5,
) -> requests.Response:
    """GET a checked response, retrying connection and server failures."""
    for attempt in range(retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is None or status < 500 or attempt == retries:
                raise WeatherAPIError(f"HTTP request failed ({status})") from exc
        except requests.exceptions.RequestException as exc:
            if attempt == retries:
                raise WeatherAPIError(f"Weather request failed: {exc}") from exc
        if backoff > 0:
            time.sleep(backoff * (2**attempt))
    raise WeatherAPIError("Weather request failed after retries")


def geocode(name: str, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Return matching locations; an empty list means no matches."""
    if not name.strip():
        raise ValueError("Location name cannot be empty")
    client = session or requests.Session()
    payload = request_json(
        client,
        GEOCODING_URL,
        params={"name": name, "count": 10, "language": "en", "format": "json"},
    )
    return payload.get("results", [])


def choose_location(candidates: list[dict[str, Any]], choice: int = 0) -> dict[str, Any]:
    """Select a configured candidate after displaying any ambiguous matches."""
    if not candidates:
        raise WeatherAPIError("No matching locations were found")
    if choice < 0 or choice >= len(candidates):
        raise ValueError(f"Location choice must be between 0 and {len(candidates) - 1}")
    return candidates[choice]


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch daily forecast values in the selected location's local timezone."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Latitude must be -90..90 and longitude -180..180")
    if not 1 <= days <= 16:
        raise ValueError("Forecast days must be between 1 and 16")
    client = session or requests.Session()
    return request_json(
        client,
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
            "forecast_days": days,
            "timezone": "auto",
        },
    )


WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def forecast_frame(payload: dict[str, Any]) -> pd.DataFrame:
    """Convert Open-Meteo daily JSON into a labeled, unit-bearing table."""
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Forecast is missing its daily data")
    columns = {
        "date": "time",
        "max_temp_c": "temperature_2m_max",
        "min_temp_c": "temperature_2m_min",
        "precipitation_mm": "precipitation_sum",
        "max_wind_kmh": "wind_speed_10m_max",
        "weather_code": "weather_code",
    }
    missing = set(columns.values()) - daily.keys()
    if missing:
        raise ValueError(f"Forecast is missing fields: {', '.join(sorted(missing))}")
    lengths = {len(daily[key]) for key in columns.values()}
    if len(lengths) != 1:
        raise ValueError("Forecast daily arrays must have equal lengths")
    frame = pd.DataFrame({name: daily[source] for name, source in columns.items()})
    frame["weather"] = frame["weather_code"].map(WEATHER_CODES).fillna("Unknown code")
    return frame


def get_met_forecast(
    latitude: float,
    longitude: float,
    contact_email: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch MET Norway data using the required identifying User-Agent."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Latitude must be -90..90 and longitude -180..180")
    if not contact_email or "@" not in contact_email or "example.edu" in contact_email:
        raise ValueError("Set your real university email before calling MET Norway")
    client = session or requests.Session()
    return request_json(
        client,
        MET_URL,
        params={"lat": round(latitude, 4), "lon": round(longitude, 4)},
        headers={"User-Agent": f"OOPWeatherAssignment/1.0 {contact_email}"},
    )
