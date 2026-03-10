"""
AI-powered city guide for Cheap Flight Finder.
Uses OpenAI API for structured destination insights.
Cautious wording for uncertain data (events, weather, etc.).
"""
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def get_city_guide(
    city: str,
    country: str = "",
    depart_date: str = "",
    return_date: str = "",
) -> dict[str, Any]:
    """
    Fetch structured city guide from OpenAI.
    Returns {success, data?, error?}.
    Uses cautious language when certainty is low.
    """
    if not city or not city.strip():
        return {"success": False, "error": "City is required"}

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; city guide unavailable")
        return {"success": False, "error": "City guide service is not configured"}

    location = f"{city.strip()}"
    if country and country.strip():
        location += f", {country.strip()}"

    date_context = ""
    if depart_date and return_date:
        date_context = f" Travel dates: {depart_date} to {return_date}."
    elif depart_date:
        date_context = f" Departure date: {depart_date}."

    prompt = f"""You are a travel assistant. Provide a brief, practical city guide for {location}.{date_context}

Respond ONLY with valid JSON in this exact structure (no markdown, no extra text):
{{
  "overview": "2-3 sentence quick overview.",
  "top_hotels": ["Hotel A", "Hotel B", "Hotel C", "Hotel D", "Hotel E"],
  "top_restaurants": ["Restaurant 1", "Restaurant 2", "Restaurant 3", "Restaurant 4", "Restaurant 5"],
  "top_kebab_restaurants": ["Kebab place 1", "Kebab place 2", "Kebab place 3", "Kebab place 4", "Kebab place 5"],
  "top_attractions": ["Museum/Landmark 1", "Museum/Landmark 2", "Museum/Landmark 3", "Place 4", "Place 5"],
  "events": "Brief note. If dates unknown, say 'Events vary by season - check local listings.'",
  "weather": "Typical weather.",
  "transport": "1-2 sentences on metro, bus, tram.",
  "transport_tips": "How to buy tickets, transport card options.",
  "airport_transfer": "How to get from airport to city center.",
  "card_vs_cash": "Whether card or cash is more commonly used.",
  "budget": "Brief daily budget hint for mid-range tourist.",
  "car_rental": "Popular car rental providers. Brief note.",
  "local_tips": "2-3 short practical tips."
}}

Rules:
- top_hotels: Exactly 5 best hotels, from MOST EXPENSIVE to CHEAPEST.
- top_restaurants: Exactly 5 best/iconic restaurants in the city.
- top_kebab_restaurants: Exactly 5 best kebab restaurants in the selected country, ranked by highest Google rating and most reviews. Use real establishment names.
- top_attractions: Exactly 5 best places to visit (museums, landmarks, parks, monuments).
- Use real, well-known establishment names when possible.
- Output only the JSON object."""

    try:
        import requests

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 1600,
            },
            timeout=25,
        )

        if resp.status_code != 200:
            logger.warning("OpenAI API error: %s %s", resp.status_code, resp.text[:200])
            return {"success": False, "error": "City guide temporarily unavailable"}

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return {"success": False, "error": "No response from city guide service"}

        content = (choices[0].get("message") or {}).get("content") or ""
        content = content.strip()
        if content.startswith("```"):
            for sep in ("```json", "```"):
                if content.startswith(sep):
                    content = content[len(sep) :].strip()
                    break
            if content.endswith("```"):
                content = content[:-3].strip()

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return {"success": False, "error": "Invalid city guide response"}

        # Ensure expected keys with fallbacks
        def _list5(key):
            v = parsed.get(key)
            return (v[:5] if isinstance(v, list) else []) if v else []

        result = {
            "overview": parsed.get("overview", ""),
            "top_hotels": _list5("top_hotels"),
            "top_restaurants": _list5("top_restaurants"),
            "top_kebab_restaurants": _list5("top_kebab_restaurants"),
            "top_attractions": _list5("top_attractions"),
            "events": parsed.get("events", ""),
            "weather": parsed.get("weather", ""),
            "transport": parsed.get("transport", ""),
            "transport_tips": parsed.get("transport_tips", ""),
            "airport_transfer": parsed.get("airport_transfer", ""),
            "card_vs_cash": parsed.get("card_vs_cash", ""),
            "budget": parsed.get("budget", ""),
            "car_rental": parsed.get("car_rental", ""),
            "local_tips": parsed.get("local_tips", ""),
        }
        return {"success": True, "data": result}

    except json.JSONDecodeError as e:
        logger.warning("City guide JSON parse error: %s", e)
        return {"success": False, "error": "Could not parse city guide"}
    except Exception as e:
        logger.exception("City guide error: %s", e)
        return {"success": False, "error": "City guide temporarily unavailable"}
