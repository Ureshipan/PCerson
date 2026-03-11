from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


WEATHER_CODES = {
    0: "ясно",
    1: "в основном ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    80: "ливень",
    81: "сильный ливень",
    82: "очень сильный ливень",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}


class WeatherService:
    def __init__(self, providers_config: dict[str, Any]) -> None:
        self.config = providers_config.get("weather", {})
        self.enabled = bool(self.config.get("enabled", False))
        self.default_location = str(self.config.get("default_location", "")).strip()
        self.language = str(self.config.get("language", "ru")).strip() or "ru"
        self.geocode_endpoint = str(
            self.config.get("geocode_endpoint", "https://geocoding-api.open-meteo.com/v1/search")
        ).rstrip("/")
        self.forecast_endpoint = str(
            self.config.get("forecast_endpoint", "https://api.open-meteo.com/v1/forecast")
        ).rstrip("/")

    def healthcheck(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "default_location": self.default_location,
            "provider": "open-meteo",
        }

    def get_weather(self, location: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "message": "Weather provider disabled"}
        resolved_location = (location or self.default_location).strip()
        if not resolved_location:
            return {"ok": False, "message": "Weather location is not specified"}
        try:
            place = self._geocode(resolved_location)
            if place is None:
                return {"ok": False, "message": f"Location not found: {resolved_location}"}
            forecast = self._forecast(place["latitude"], place["longitude"], place.get("timezone", "auto"))
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "message": f"Weather lookup failed: {exc}"}

        current = forecast.get("current", {})
        daily = forecast.get("daily", {})
        today_index = 0
        result = {
            "ok": True,
            "message": f"Weather fetched for {place['name']}",
            "data": {
                "location": {
                    "name": place["name"],
                    "country": place.get("country", ""),
                    "timezone": place.get("timezone", ""),
                },
                "current": {
                    "temperature_c": current.get("temperature_2m"),
                    "apparent_temperature_c": current.get("apparent_temperature"),
                    "wind_speed_kmh": current.get("wind_speed_10m"),
                    "weather_code": current.get("weather_code"),
                    "weather_text": WEATHER_CODES.get(current.get("weather_code"), "неизвестно"),
                },
                "today": {
                    "temperature_max_c": (daily.get("temperature_2m_max") or [None])[today_index],
                    "temperature_min_c": (daily.get("temperature_2m_min") or [None])[today_index],
                    "precipitation_probability_max": (daily.get("precipitation_probability_max") or [None])[today_index],
                },
            },
        }
        return result

    def _geocode(self, location: str) -> dict[str, Any] | None:
        query = urllib.parse.urlencode(
            {
                "name": location,
                "count": 1,
                "language": self.language,
                "format": "json",
            }
        )
        with urllib.request.urlopen(f"{self.geocode_endpoint}?{query}", timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        results = payload.get("results", [])
        if not results:
            return None
        first = results[0]
        return {
            "name": first.get("name", location),
            "country": first.get("country", ""),
            "latitude": first.get("latitude"),
            "longitude": first.get("longitude"),
            "timezone": first.get("timezone", "auto"),
        }

    def _forecast(self, latitude: float, longitude: float, timezone: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone or "auto",
                "forecast_days": 2,
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            }
        )
        with urllib.request.urlopen(f"{self.forecast_endpoint}?{query}", timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
