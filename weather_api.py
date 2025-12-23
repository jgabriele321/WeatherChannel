"""
Weather API - Fetches forecast data from OpenWeatherMap
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# City configurations
CITIES = {
    "austin": {
        "lat": 30.2672,
        "lon": -97.7431,
        "name": "Austin",
        "region": "Metro",
        "units": "imperial",  # Fahrenheit
        "nearby": [
            {"name": "Houston", "lat": 29.7604, "lon": -95.3698},
            {"name": "Dallas", "lat": 32.7767, "lon": -96.7970},
            {"name": "San Antonio", "lat": 29.4241, "lon": -98.4936},
            {"name": "El Paso", "lat": 31.7619, "lon": -106.4850},
        ]
    },
    "london": {
        "lat": 51.5074,
        "lon": -0.1278,
        "name": "London",
        "region": "Metro",
        "units": "metric",  # Celsius
        "nearby": [
            {"name": "Paris", "lat": 48.8566, "lon": 2.3522},
            {"name": "Berlin", "lat": 52.5200, "lon": 13.4050},
            {"name": "Amsterdam", "lat": 52.3676, "lon": 4.9041},
            {"name": "Brussels", "lat": 50.8503, "lon": 4.3517},
        ]
    }
}

# Weather condition to icon mapping
CONDITION_ICONS = {
    "Clear": "sun",
    "Clouds": "clouds",
    "Rain": "rain",
    "Drizzle": "rain",
    "Thunderstorm": "thunderstorm",
    "Snow": "snow",
    "Mist": "clouds",
    "Fog": "clouds",
    "Haze": "clouds",
}


def get_icon_name(condition: str) -> str:
    """Map weather condition to icon name."""
    return CONDITION_ICONS.get(condition, "clouds")


def fetch_forecast(city_key: str) -> dict:
    """
    Fetch 3-day forecast for a city.
    Returns cached data if API fails.
    """
    city = CITIES[city_key]
    cache_file = CACHE_DIR / f"{city_key}_forecast.json"
    
    try:
        # Fetch from OpenWeatherMap One Call API 3.0
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": city["lat"],
            "lon": city["lon"],
            "appid": API_KEY,
            "units": city["units"],
            "cnt": 24,  # 3 days of 3-hour forecasts
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Process into daily forecasts
        forecast = process_forecast(data, city)
        
        # Cache successful response
        with open(cache_file, "w") as f:
            json.dump(forecast, f)
        
        print(f"✓ Fetched forecast for {city['name']}")
        return forecast
        
    except Exception as e:
        print(f"✗ API error for {city['name']}: {e}")
        
        # Try to load cached data
        if cache_file.exists():
            print(f"  Using cached data for {city['name']}")
            with open(cache_file) as f:
                return json.load(f)
        
        # Return fallback data
        return get_fallback_forecast(city)


def process_forecast(data: dict, city: dict) -> dict:
    """Process API response into our format."""
    days = {}
    
    for item in data.get("list", []):
        dt = datetime.fromtimestamp(item["dt"])
        day_key = dt.strftime("%Y-%m-%d")
        
        if day_key not in days:
            days[day_key] = {
                "date": dt,
                "day_name": dt.strftime("%a").upper(),
                "temps": [],
                "conditions": [],
            }
        
        days[day_key]["temps"].append(item["main"]["temp"])
        days[day_key]["conditions"].append(item["weather"][0]["main"])
    
    # Convert to list and calculate high/low
    forecasts = []
    for day_key in sorted(days.keys())[:3]:  # First 3 days
        day = days[day_key]
        temps = day["temps"]
        
        # Most common condition
        condition = max(set(day["conditions"]), key=day["conditions"].count)
        
        forecasts.append({
            "day_name": day["day_name"],
            "high": round(max(temps)),
            "low": round(min(temps)),
            "condition": condition,
            "icon": get_icon_name(condition),
            "description": get_description(condition),
        })
    
    return {
        "city": city["name"],
        "region": city["region"],
        "units": city["units"],
        "unit_symbol": "°F" if city["units"] == "imperial" else "°C",
        "timestamp": datetime.now().isoformat(),
        "forecasts": forecasts,
    }


def get_description(condition: str) -> str:
    """Get readable description for condition."""
    descriptions = {
        "Clear": "Sunny",
        "Clouds": "Cloudy",
        "Rain": "Rainy",
        "Drizzle": "Light Rain",
        "Thunderstorm": "T'storms",
        "Snow": "Snow",
        "Mist": "Misty",
        "Fog": "Foggy",
        "Haze": "Hazy",
    }
    return descriptions.get(condition, condition)


def get_fallback_forecast(city: dict) -> dict:
    """Return fallback data when API fails and no cache."""
    now = datetime.now()
    days = []
    
    for i in range(3):
        day = now.replace(day=now.day + i)
        days.append({
            "day_name": day.strftime("%a").upper(),
            "high": 75 if city["units"] == "imperial" else 24,
            "low": 55 if city["units"] == "imperial" else 13,
            "condition": "Clouds",
            "icon": "clouds",
            "description": "Cloudy",
        })
    
    return {
        "city": city["name"],
        "region": city["region"],
        "units": city["units"],
        "unit_symbol": "°F" if city["units"] == "imperial" else "°C",
        "timestamp": now.isoformat(),
        "forecasts": days,
    }


def fetch_nearby_weather(city_key: str) -> list:
    """Fetch current weather for nearby cities (for map)."""
    city = CITIES[city_key]
    nearby_weather = []
    
    for nearby in city["nearby"]:
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": nearby["lat"],
                "lon": nearby["lon"],
                "appid": API_KEY,
                "units": city["units"],
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            nearby_weather.append({
                "name": nearby["name"],
                "lat": nearby["lat"],
                "lon": nearby["lon"],
                "temp": round(data["main"]["temp"]),
                "condition": data["weather"][0]["main"],
                "icon": get_icon_name(data["weather"][0]["main"]),
            })
        except Exception as e:
            print(f"  Warning: Could not fetch {nearby['name']}: {e}")
            nearby_weather.append({
                "name": nearby["name"],
                "lat": nearby["lat"],
                "lon": nearby["lon"],
                "temp": 70 if city["units"] == "imperial" else 21,
                "condition": "Clouds",
                "icon": "clouds",
            })
    
    return nearby_weather


if __name__ == "__main__":
    # Test the API
    print("Testing Weather API...")
    
    austin = fetch_forecast("austin")
    print(f"\nAustin forecast:")
    for day in austin["forecasts"]:
        print(f"  {day['day_name']}: {day['high']}/{day['low']}°F - {day['description']}")
    
    london = fetch_forecast("london")
    print(f"\nLondon forecast:")
    for day in london["forecasts"]:
        print(f"  {day['day_name']}: {day['high']}/{day['low']}°C - {day['description']}")

