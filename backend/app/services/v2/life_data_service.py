from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

import httpx

from ...config import settings


@dataclass
class WeatherSnapshot:
    city: str
    temperature_c: float
    condition: str


@dataclass
class PlaceSuggestion:
    name: str
    distance_km: float
    rating: float
    cuisine: str


class LifeDataService:
    async def weather_for_city(self, city: str) -> Optional[WeatherSnapshot]:
        city_name = (city or "").strip()
        if not city_name:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                geo = await client.get(
                    settings.LIFE_GEOCODE_BASE_URL,
                    params={"name": city_name, "count": 1, "language": "en", "format": "json"},
                )
                geo.raise_for_status()
                gdata = geo.json()
                results = gdata.get("results") or []
                if not results:
                    return None
                lat = float(results[0]["latitude"])
                lon = float(results[0]["longitude"])
                canonical = str(results[0].get("name") or city_name)
                weather = await client.get(
                    settings.LIFE_WEATHER_BASE_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,weather_code",
                    },
                )
                weather.raise_for_status()
                wdata = weather.json()
                current = wdata.get("current") or {}
                temp = float(current.get("temperature_2m", 0.0))
                code = int(current.get("weather_code", 0))
                return WeatherSnapshot(
                    city=canonical,
                    temperature_c=temp,
                    condition=self._weather_label(code),
                )
        except Exception:
            return None

    async def nearby_restaurants(self, query: str, preference: str = "") -> List[PlaceSuggestion]:
        if settings.LIFE_PLACES_API_URL.strip():
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        settings.LIFE_PLACES_API_URL,
                        params={"query": query, "preference": preference},
                        headers={"Authorization": f"Bearer {settings.LIFE_PLACES_API_KEY}"} if settings.LIFE_PLACES_API_KEY else {},
                    )
                    response.raise_for_status()
                    rows = response.json().get("results", [])
                    return [
                        PlaceSuggestion(
                            name=str(item.get("name", "Restaurant")),
                            distance_km=float(item.get("distance_km", 1.0)),
                            rating=float(item.get("rating", 4.2)),
                            cuisine=str(item.get("cuisine", "mixed")),
                        )
                        for item in rows[:5]
                    ]
            except Exception:
                pass
        pref = (preference or "mixed").lower()
        return [
            PlaceSuggestion(name="Green Bowl Cafe", distance_km=0.6, rating=4.5, cuisine="veg" if "veg" in pref else "healthy"),
            PlaceSuggestion(name="Spice Route Kitchen", distance_km=1.2, rating=4.3, cuisine="indian"),
            PlaceSuggestion(name="Quick Bite Hub", distance_km=0.9, rating=4.1, cuisine="multi"),
        ]

    def lunch_menu(self) -> List[str]:
        raw = (settings.LIFE_CAFETERIA_MENU_JSON or "").strip()
        if raw:
            try:
                payload = json.loads(raw)
                if isinstance(payload, list):
                    return [str(item) for item in payload if str(item).strip()][:10]
            except Exception:
                pass
        return ["Dal tadka", "Jeera rice", "Grilled veggies", "Curd", "Fruit bowl"]

    def _weather_label(self, weather_code: int) -> str:
        mapping = {
            0: "clear",
            1: "mostly clear",
            2: "partly cloudy",
            3: "cloudy",
            45: "foggy",
            48: "foggy",
            51: "light drizzle",
            53: "drizzle",
            55: "heavy drizzle",
            61: "light rain",
            63: "rain",
            65: "heavy rain",
            80: "rain showers",
            81: "rain showers",
            82: "heavy showers",
            95: "thunderstorm",
        }
        return mapping.get(weather_code, "mixed conditions")
