import requests
from django.conf import settings
from django.shortcuts import render


def fetch_weather(city: str):
    """
    OpenWeatherMap API-dən hava məlumatı gətirən funksiya.
    """
    api_key = getattr(settings, "OPENWEATHER_API_KEY", "")
    if not api_key:
        return None, "Error: API key not configured in settings.py"

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}

    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.RequestException as e:
        return None, f"Error: request failed ({e})"

    if resp.status_code == 200:
        data = resp.json()
        city_name = data.get("name", city)
        temp = data["main"]["temp"]
        weather_desc = data["weather"][0]["description"]
        text = f"Weather in {city_name}: {temp}°C, {weather_desc}"
        return text, None
    else:
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text
        return None, f"Error: {resp.status_code} {err_msg}"


def weather_project_view(request):
    city = request.GET.get("city", "").strip()
    result, error = None, None

    if city:
        result, error = fetch_weather(city)

    return render(request, "weather_app.html", {
        "city": city,
        "result": result,
        "error": error,
    })
