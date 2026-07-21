from langchain_core.tools import tool
import httpx

@tool
async def weather_tool(location: str) -> str:
    """Get current weather for a location (city name)."""
    # Return realistic weather data or call open-meteo API
    try:
        async with httpx.AsyncClient() as client:
            # Open-Meteo geocoding + weather fallback
            resp = await client.get(f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1")
            data = resp.json()
            if data.get("results"):
                lat = data["results"][0]["latitude"]
                lon = data["results"][0]["longitude"]
                name = data["results"][0]["name"]
                w_resp = await client.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true")
                w_data = w_resp.json().get("current_weather", {})
                temp = w_data.get("temperature", "N/A")
                wind = w_data.get("windspeed", "N/A")
                return f"Weather in {name}: {temp}°C, Wind Speed: {wind} km/h"
    except Exception:
        pass
    return f"Weather for {location}: 22°C, Partly Cloudy, Humidity 45% (Mocked)"
