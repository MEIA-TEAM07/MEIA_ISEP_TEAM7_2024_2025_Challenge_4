import requests
import time
from config import WEATHER_API_KEY, WEATHER_LAT, WEATHER_LON, WEATHER_UPDATE_INTERVAL

_last_weather = None
_last_fetch = 0

def fetch_weather():
    url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"lat={WEATHER_LAT}&lon={WEATHER_LON}&appid={WEATHER_API_KEY}&units=metric"
    )
    try:
        resp = requests.get(url)
        data = resp.json()
        # Parse only the fields you want:
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        return {
            "temperature": temp,
            "humidity": humidity,
            "wind_speed": wind_speed
        }
    except Exception as e:
        print(f"Failed to fetch weather data: {e}")
        # You might want to return last known or fallback values
        return {
            "temperature": 20.0,
            "humidity": 60.0,
            "wind_speed": 5.0
        }
    
def get_current_weather():
    global _last_weather, _last_fetch
    now = time.time()
    if not _last_weather or now - _last_fetch > WEATHER_UPDATE_INTERVAL:
        _last_weather = fetch_weather()
        _last_fetch = now
    return _last_weather