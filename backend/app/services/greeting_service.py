from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass
import os
import json
import aiohttp


# Weather condition types and their tips
WEATHER_TIPS = {
    "sunny": "☀️ Bright day ahead! Don't forget sunscreen if you're heading out.",
    "cloudy": "☁️ Overcast skies - great for a walk, no sunglasses needed!",
    "rainy": "🌧️ Rainy vibes! Keep an umbrella handy and stay cozy.",
    "stormy": "⛈️ Stormy weather - stay safe indoors if you can.",
    "snowy": "❄️ Snow day! Bundle up and be careful on the roads.",
    "foggy": "🌫️ Foggy morning - drive safely and take it slow.",
    "windy": "💨 It's windy! Secure loose items and hold onto your hat.",
    "hot": "🔥 Scorching heat! Stay hydrated and find some AC.",
    "cold": "🥶 Bundle up! Hot tea or coffee will warm you right up.",
    "default": "🌡️ Whatever the weather, make it a great day!"
}

# Weather condition to category mapping (OpenWeatherMap condition codes)
WEATHER_CONDITIONS = {
    # Thunderstorm
    200: "stormy", 201: "stormy", 202: "stormy", 210: "stormy", 211: "stormy",
    212: "stormy", 221: "stormy", 232: "stormy",
    # Drizzle
    300: "rainy", 301: "rainy", 302: "rainy", 310: "rainy", 311: "rainy",
    312: "rainy", 314: "rainy",
    # Rain
    500: "rainy", 501: "rainy", 502: "rainy", 503: "rainy", 504: "rainy",
    511: "cold", 520: "rainy", 521: "rainy", 522: "rainy", 531: "rainy",
    # Snow
    600: "snowy", 601: "snowy", 602: "snowy", 611: "snowy", 612: "snowy",
    613: "snowy", 615: "snowy", 616: "snowy", 620: "snowy", 621: "snowy",
    622: "snowy",
    # Atmosphere (fog, mist, etc.)
    701: "foggy", 711: "foggy", 721: "foggy", 731: "foggy", 741: "foggy",
    751: "foggy", 761: "foggy", 762: "foggy", 771: "foggy", 781: "foggy",
    # Clear
    800: "sunny",
    # Clouds
    801: "sunny", 802: "cloudy", 803: "cloudy", 804: "cloudy",
}


@dataclass
class Greeting:
    message: str
    emoji: str
    tip: str


GREETINGS = {
    "morning": Greeting(
        message="Good morning!",
        emoji="🌅",
        tip="Start your day with a glass of water and a positive thought. You've got this!"
    ),
    "afternoon": Greeting(
        message="Good afternoon!",
        emoji="☀️",
        tip="Take a quick break and stretch. A short walk can boost your productivity."
    ),
    "evening": Greeting(
        message="Good evening!",
        emoji="🌙",
        tip="Reflect on what you accomplished today. Every step forward counts!"
    ),
    "night": Greeting(
        message="Hello night owl!",
        emoji="🦉",
        tip="Remember to rest well. Sleep is essential for peak performance tomorrow."
    )
}


def _get_time_period(hour: int) -> str:
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:
        return "night"


def _get_weather_category(weather_id: int) -> str:
    return WEATHER_CONDITIONS.get(weather_id, "default")


def _get_weather_tip(weather_id: int, temperature: Optional[float] = None) -> str:
    category = _get_weather_category(weather_id)
    tip = WEATHER_TIPS.get(category, WEATHER_TIPS["default"])
    
    if temperature is not None:
        if temperature > 35:
            return WEATHER_TIPS["hot"]
        elif temperature < 5:
            return WEATHER_TIPS["cold"]
    
    return tip


def _parse_env_location() -> Optional[str]:
    env_file = os.environ.get("WEATHER_LOCATION")
    if env_file:
        return env_file
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    env_path = os.path.join(project_root, ".env")
    
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("WEATHER_LOCATION="):
                    return line.split("=", 1)[1].strip()
    
    return None


async def fetch_weather_async(location: Optional[str] = None) -> Optional[Dict]:
    api_key = os.environ.get("OPENWEATHER_API_KEY") or os.environ.get("WEATHER_API_KEY")
    
    resolved_location = location or _parse_env_location() or "London"
    
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params: Dict[str, str] = {"q": resolved_location, "units": "metric"}
        if api_key:
            params["appid"] = api_key
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    weather = data.get("weather", [{}])[0]
                    main = data.get("main", {})
                    return {
                        "condition_id": weather.get("id", 800),
                        "temperature": main.get("temp"),
                        "description": weather.get("description", ""),
                    }
    except Exception:
        pass
    
    return None


def get_weather_tip_sync(location: Optional[str] = None) -> Optional[str]:
    api_key = os.environ.get("OPENWEATHER_API_KEY") or os.environ.get("WEATHER_API_KEY")
    
    if not api_key:
        return None
    
    resolved_location = location or _parse_env_location() or "London"
    
    try:
        import urllib.request
        url = f"https://api.openweathermap.org/data/2.5/weather?q={resolved_location}&appid={api_key}&units=metric"
        
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            weather = data.get("weather", [{}])[0]
            main = data.get("main", {})
            return _get_weather_tip(weather.get("id", 800), main.get("temp"))
    except Exception:
        pass
    
    return None


def get_time_based_greeting(
    hour: Optional[int] = None,
    weather_location: Optional[str] = None,
    include_weather_tip: bool = True,
) -> Dict:
    if hour is None:
        hour = datetime.utcnow().hour
    
    period = _get_time_period(hour)
    greeting = GREETINGS[period]
    
    weather_tip = None
    if include_weather_tip:
        weather_tip = get_weather_tip_sync(weather_location)
    
    return {
        "message": greeting.message,
        "emoji": greeting.emoji,
        "tip": greeting.tip,
        "period": period,
        "weather_tip": weather_tip,
    }