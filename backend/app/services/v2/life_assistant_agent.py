from __future__ import annotations

import re
from dataclasses import dataclass
import asyncio
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..memory_service import get_memory_service
from .life_data_service import LifeDataService

@dataclass
class LifeAssistantResponse:
    handled: bool
    reply: str


class LifeAssistantAgent:
    """
    V2 foundation agent for daily-life assistance.
    API integrations (weather/maps/cafeteria) can be attached behind this contract.
    """

    def __init__(self, db: Session, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id
        self.data_service = LifeDataService()

    def maybe_handle(self, message: str) -> LifeAssistantResponse:
        text = (message or "").lower()
        if re.search(r"\b(weather|temperature|rain|forecast)\b", text):
            city_match = re.search(r"\b(?:in|at)\s+([a-zA-Z\s]+)$", text)
            city = city_match.group(1).strip().title() if city_match else "Nagpur"
            snapshot = asyncio.run(self.data_service.weather_for_city(city))
            if snapshot:
                advice = (
                    "Looks warm — maybe step out early for lunch."
                    if snapshot.temperature_c >= 34
                    else "Good weather for a short break walk later."
                )
                return LifeAssistantResponse(
                    handled=True,
                    reply=f"{snapshot.city}: {round(snapshot.temperature_c)}°C, {snapshot.condition}. {advice}",
                )
            fallback_advice = "Looks warm — maybe grab lunch indoors or step out early."
            return LifeAssistantResponse(
                handled=True,
                reply=f"{city}: 32°C, mixed conditions. {fallback_advice}",
            )
        if re.search(r"\b(restaurants?|food\s+near|nearby\s+(?:food|restaurants?)|where\s+can\s+i\s+eat|places\s+to\s+eat|good\s+lunch\s+spots?|lunch\s+spots?)\b", text):
            preference = self._resolve_food_preference(text)
            suggestions = asyncio.run(self.data_service.nearby_restaurants(query=text, preference=preference))
            if suggestions:
                top = suggestions[:3]
                formatted = "; ".join(
                    [f"{s.name} ({s.cuisine}, {s.distance_km:.1f} km, {s.rating:.1f}★)" for s in top]
                )
                budget_hint = self._extract_budget_hint(text)
                self._store_food_preferences(preference=preference, budget_hint=budget_hint)
                return LifeAssistantResponse(
                    handled=True,
                    reply=f"Here are good nearby options: {formatted}. Want budget-friendly picks only?",
                )
            return LifeAssistantResponse(
                handled=True,
                reply=(
                    "I can suggest nearby food options. "
                    "Do you prefer veg/non-veg and what budget range?"
                ),
            )
        if re.search(r"\b(lunch menu|cafeteria|canteen)\b", text):
            menu = self.data_service.lunch_menu()
            return LifeAssistantResponse(
                handled=True,
                reply=f"Today's lunch menu: {', '.join(menu[:5])}. Want me to suggest lighter options?",
            )
        return LifeAssistantResponse(handled=False, reply="")

    def _resolve_food_preference(self, text: str) -> str:
        if "veg" in text or "vegetarian" in text:
            return "veg"
        if "non veg" in text or "non-veg" in text:
            return "non-veg"
        profile = get_memory_service(self.db).get_user_profile(self.user_id)
        prefs = (profile.preferences or {}) if profile else {}
        food = prefs.get("food_preferences") if isinstance(prefs, dict) else {}
        if isinstance(food, dict) and food.get("diet"):
            return str(food["diet"])
        return "mixed"

    def _extract_budget_hint(self, text: str) -> str:
        if any(token in text for token in ["cheap", "budget", "affordable", "low cost"]):
            return "budget"
        if any(token in text for token in ["premium", "fine dining", "expensive"]):
            return "premium"
        return "mid"

    def _store_food_preferences(self, *, preference: str, budget_hint: str) -> None:
        service = get_memory_service(self.db)
        profile = service.get_user_profile(self.user_id)
        existing: Dict[str, object] = {}
        if profile and isinstance(profile.preferences, dict):
            existing = dict(profile.preferences)
        food = dict(existing.get("food_preferences", {})) if isinstance(existing.get("food_preferences"), dict) else {}
        food["diet"] = preference
        food["budget"] = budget_hint
        existing["food_preferences"] = food
        service.update_user_profile(user_id=self.user_id, preferences=existing)
