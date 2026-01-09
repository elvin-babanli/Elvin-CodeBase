from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse

import requests
from collections import defaultdict, Counter
from datetime import datetime, timezone as tz
import calendar

OW_ICON = "https://openweathermap.org/img/wn/{icon}@2x.png"


def _get_json(url, params, timeout=25):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        try:
            return r.status_code, r.json(), None
        except Exception:
            return r.status_code, {"message": r.text}, None
    except requests.exceptions.Timeout:
        return 0, None, "timeout"
    except requests.exceptions.RequestException as e:
        return 0, None, f"network_error: {str(e)}"


def _fmt_local_hhmm(unix_ts: int, tz_offset_seconds: int):
    if not unix_ts:
        return None
    return datetime.fromtimestamp(unix_ts + tz_offset_seconds, tz=tz.utc).strftime("%H:%M")


def _weekday_date_from_yyyy_mm_dd(d: str):
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return calendar.day_name[dt.weekday()], dt.strftime("%b %d")
    except Exception:
        return "", d


def _fetch_weather_portfolio_shape(city: str):
    api_key = getattr(settings, "OPENWEATHER_API_KEY", "")
    if not api_key:
        return None, None, "Error: API key not configured in settings.py (OPENWEATHER_API_KEY)"

    # 1) geocode city -> lat/lon
    geo_url = "https://api.openweathermap.org/geo/1.0/direct"
    code, geo, err = _get_json(geo_url, {"q": city, "limit": 1, "appid": api_key})
    if err:
        return None, None, (
            "OpenWeather geocoding failed: "
            f"{err}. (Network/VPN/Firewall may block api.openweathermap.org)"
        )
    if code != 200 or not isinstance(geo, list) or not geo:
        return None, None, "City not found."

    lat = float(geo[0].get("lat", 0.0))
    lon = float(geo[0].get("lon", 0.0))
    country = geo[0].get("country", "")
    city_name = geo[0].get("name", city)

    # 2) current weather
    w_url = "https://api.openweathermap.org/data/2.5/weather"
    code, w, err = _get_json(w_url, {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"})
    if err:
        return None, None, f"OpenWeather current weather failed: {err}."
    if code != 200 or not isinstance(w, dict):
        msg = (w or {}).get("message", "weather fetch failed") if isinstance(w, dict) else "weather fetch failed"
        return None, None, msg

    weather0 = (w.get("weather") or [{}])[0]
    main = w.get("main", {}) or {}
    wind = w.get("wind", {}) or {}
    sys = w.get("sys", {}) or {}

    tz_offset = int(w.get("timezone", 0))  # seconds
    sunrise_ts = int(sys.get("sunrise", 0) or 0)
    sunset_ts = int(sys.get("sunset", 0) or 0)

    icon_code = weather0.get("icon")

    current = {
        "city": w.get("name", city_name),
        "country": country or sys.get("country", ""),

        "temp": round(float(main.get("temp", 0.0))),
        "feels_like": round(float(main.get("feels_like", 0.0))),
        "humidity": int(main.get("humidity", 0)),
        "wind_speed": float(wind.get("speed", 0.0)),

        "description": (weather0.get("description") or "—").capitalize(),
        "icon_url": OW_ICON.format(icon=icon_code) if icon_code else None,

        "sunrise": _fmt_local_hhmm(sunrise_ts, tz_offset) if sunrise_ts else None,
        "sunset": _fmt_local_hhmm(sunset_ts, tz_offset) if sunset_ts else None,
    }

    # 3) forecast -> daily summaries
    f_url = "https://api.openweathermap.org/data/2.5/forecast"
    code, f, err = _get_json(f_url, {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"})
    if err:
        return current, [], f"OpenWeather forecast failed: {err}."
    if code != 200 or not isinstance(f, dict) or "list" not in f:
        msg = (f or {}).get("message", "forecast fetch failed") if isinstance(f, dict) else "forecast fetch failed"
        return current, [], msg

    by_date = defaultdict(list)
    for item in f.get("list", []):
        dt_txt = item.get("dt_txt")
        if not dt_txt or len(dt_txt) < 10:
            continue
        by_date[dt_txt[:10]].append(item)

    dates = sorted(by_date.keys())[:5]
    daily = []

    for d in dates:
        items = by_date[d]

        temps = []
        icons = []
        descs = []

        for x in items:
            t = (x.get("main") or {}).get("temp")
            if isinstance(t, (int, float)):
                temps.append(float(t))

            w0 = (x.get("weather") or [{}])[0]
            if w0.get("icon"):
                icons.append(w0.get("icon"))
            if w0.get("description"):
                descs.append((w0.get("description") or "").capitalize())

        if not temps:
            continue

        icon = Counter(icons).most_common(1)[0][0] if icons else None
        desc = Counter(descs).most_common(1)[0][0] if descs else "—"

        weekday, date_str = _weekday_date_from_yyyy_mm_dd(d)

        daily.append({
            "weekday": weekday,
            "date": date_str,
            "temp_min": round(min(temps)),
            "temp_max": round(max(temps)),
            "description": desc,
            "icon_url": OW_ICON.format(icon=icon) if icon else None,
        })

    return current, daily, None


def weather_project_view(request):
    city = (request.GET.get("city") or "").strip()
    current = None
    daily = []
    error = None

    if city:
        current, daily, error = _fetch_weather_portfolio_shape(city)

    return render(request, "weather_app.html", {
        "city": city,
        "current": current,
        "daily": daily,
        "error": error,
    })


# optional: ajax üçün api
def weather_api(request):
    city = (request.GET.get("city") or "").strip()
    if not city:
        return JsonResponse({"error": "city is required"}, status=400)

    current, daily, err = _fetch_weather_portfolio_shape(city)
    if err:
        return JsonResponse({"error": err}, status=503)

    return JsonResponse({"current": current, "daily": daily}, status=200)
