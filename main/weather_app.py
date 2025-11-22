import requests
from django.conf import settings
from django.shortcuts import render
from datetime import datetime
import calendar
from collections import Counter, defaultdict

OW_ICON = "https://openweathermap.org/img/wn/{icon}@2x.png"


def _fmt_hhmm_from_unix(ts: int, tz_offset_sec: int) -> str:
    """Unix timestamp + timezone offset (seconds) -> 'HH:MM' (local)."""
    if ts is None:
        return ""
    dt = datetime.utcfromtimestamp(ts + tz_offset_sec)
    return dt.strftime("%H:%M")


def _weekday_date_from_iso(iso_str: str):
    """
    'YYYY-MM-DD HH:MM:SS' -> (WeekdayName, 'Mon DD')
    """
    try:
      dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
      # bəzi hallarda format fərqli ola bilər
      try:
        dt = datetime.fromisoformat(iso_str)
      except Exception:
        return "", iso_str
    return calendar.day_name[dt.weekday()], dt.strftime("%b %d")


def fetch_current(city: str):
    """
    Current weather (free endpoint).
    Returns: dict(current), None on error OR (None, error_msg)
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

    if resp.status_code != 200:
        try:
            err = resp.json().get("message", resp.text)
        except Exception:
            err = resp.text
        return None, f"Error: {resp.status_code} {err}"

    data = resp.json()
    weather = (data.get("weather") or [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})
    sys_ = data.get("sys", {})

    tz_offset = data.get("timezone", 0)  # seconds offset from UTC

    current = {
        "city": data.get("name", city),
        "country": sys_.get("country"),
        "temp": round(main.get("temp", 0)),
        "feels_like": round(main.get("feels_like", 0)),
        "humidity": main.get("humidity", 0),
        "wind_speed": wind.get("speed", 0),
        "description": (weather.get("description") or "").capitalize(),
        "icon_url": OW_ICON.format(icon=weather.get("icon")) if weather.get("icon") else None,
        "sunrise": _fmt_hhmm_from_unix(sys_.get("sunrise"), tz_offset) if sys_.get("sunrise") else None,
        "sunset": _fmt_hhmm_from_unix(sys_.get("sunset"), tz_offset) if sys_.get("sunset") else None,
    }
    return current, None


def fetch_forecast_5d(city: str):
    """
    5-day / 3-hour forecast (free endpoint).
    Biz 3-saatlıq blokları günə görə qruplaşdırırıq və hər gün üçün:
      - min temp
      - max temp
      - dominant (ən çox görülən) icon/description
    """
    api_key = getattr(settings, "OPENWEATHER_API_KEY", "")
    if not api_key:
        return None, "Error: API key not configured in settings.py"

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric"}

    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.RequestException as e:
        return None, f"Error: forecast request failed ({e})"

    if resp.status_code == 401:
        return None, "Forecast is not available for your API key."
    if resp.status_code != 200:
        try:
            err = resp.json().get("message", resp.text)
        except Exception:
            err = resp.text
        return None, f"Error: {resp.status_code} {err}"

    data = resp.json()
    items = data.get("list", [])
    if not items:
        return [], None

    # Günə görə toplulaşdır
    by_day = defaultdict(list)
    for it in items:
        dt_txt = it.get("dt_txt")  # 'YYYY-MM-DD HH:MM:SS'
        if not dt_txt:
            # bəzi cavablarda yalnız dt ola bilər
            try:
                dt = datetime.utcfromtimestamp(it.get("dt"))
                dt_txt = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
        day_key = dt_txt.split(" ")[0]  # YYYY-MM-DD
        by_day[day_key].append(it)

    daily = []
    for day_key in sorted(by_day.keys())[:5]:  # yalnız 5 gün
        bucket = by_day[day_key]
        temps = [b.get("main", {}).get("temp") for b in bucket if b.get("main")]
        tmins = [b.get("main", {}).get("temp_min") for b in bucket if b.get("main")]
        tmaxs = [b.get("main", {}).get("temp_max") for b in bucket if b.get("main")]

        # icon/description üçün dominantı seç
        icons = []
        descs = []
        for b in bucket:
            w = (b.get("weather") or [{}])[0]
            if w.get("icon"):
                icons.append(w.get("icon"))
            if w.get("description"):
                descs.append(w.get("description").capitalize())
        icon = Counter(icons).most_common(1)[0][0] if icons else None
        desc = Counter(descs).most_common(1)[0][0] if descs else ""

        weekday, date_str = _weekday_date_from_iso(day_key + " 00:00:00")
        daily.append({
            "weekday": weekday,
            "date": date_str,
            "temp_min": round(min(tmins) if tmins else (min(temps) if temps else 0)),
            "temp_max": round(max(tmaxs) if tmaxs else (max(temps) if temps else 0)),
            "description": desc,
            "icon_url": OW_ICON.format(icon=icon) if icon else None,
        })

    return daily, None


def weather_project_view(request):
    city = request.GET.get("city", "").strip()
    current = None
    daily = []
    error = None

    if city:
        current, error = fetch_current(city)
        if not error:
            daily, error = fetch_forecast_5d(city)

    return render(request, "weather_app.html", {
        "city": city,
        "current": current,
        "daily": daily,
        "error": error,
    })
