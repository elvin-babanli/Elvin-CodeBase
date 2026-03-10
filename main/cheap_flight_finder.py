# main/cheap_flight_finder.py
import json
import logging
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from main import airport_data
from main.flight_normalizer import apply_badges, normalize_all_offers

# Session key for flight context (auth redirect flow)
CFF_SESSION_KEY = "cff_selected_flight"
CFF_SESSION_MAX_AGE = 3600  # 1 hour

load_dotenv()

logger = logging.getLogger(__name__)

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
OFFERS_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
LOCATIONS_URL = "https://test.api.amadeus.com/v1/reference-data/locations"

# Cache for Amadeus location search (keyword -> (results, timestamp))
_LOCATIONS_CACHE: dict[str, tuple[list[dict[str, Any]], float]] = {}
_LOCATIONS_CACHE_TTL = 300  # seconds
_MIN_KEYWORD_LEN = 2


class AmadeusError(Exception):
    pass


def get_access_token() -> str:
    if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:
        raise AmadeusError("AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET not set.")

    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET,
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=15)
    if resp.status_code != 200:
        raise AmadeusError(f"Failed to get token: {resp.text}")
    return resp.json().get("access_token")


def get_offers(
    origin: str,
    destination: str,
    depart_date: str,
    currency: str,
    max_items: int = 10,
    return_date: str | None = None,
    adults: int = 1,
) -> dict:
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, Any] = {
        "originLocationCode": origin.upper().strip(),
        "destinationLocationCode": destination.upper().strip(),
        "departureDate": depart_date.strip(),
        "adults": max(1, min(9, int(adults) if adults else 1)),
        "currencyCode": currency.upper().strip(),
        "max": max(1, min(250, max_items)),
    }
    if return_date and return_date.strip():
        params["returnDate"] = return_date.strip()
    resp = requests.get(OFFERS_URL, headers=headers, params=params, timeout=20)
    if resp.status_code != 200:
        raise AmadeusError(f"Failed to get offers: {resp.text}")
    return resp.json()


def _fmt_time(iso_str: str) -> str:
    """
    ISO datetime (YYYY-MM-DDTHH:MM:SS) dəyərini sadə HH:MM formatına çevirir.
    Məs: '2025-01-10T07:45:00' -> '07:45'
    """
    if not iso_str or "T" not in iso_str:
        return ""
    try:
        return iso_str.split("T", 1)[1][:5]
    except Exception:
        return iso_str


def pick_cheapest(offers: dict) -> dict | None:
    """
    Gələn offer-lərdən ən ucuzunu seç və
    qiymət + bütün marşrut seqmentlərini (vaxtlarla) qaytar.
    """
    flights = []

    for offer in offers.get("data", []):
        try:
            price = float(offer["price"]["total"])
        except Exception:
            continue

        segments_list = []
        for itinerary in offer.get("itineraries", []):
            for segment in itinerary.get("segments", []):
                carrier_code = segment.get("carrierCode")
                carrier = offers.get("dictionaries", {}).get("carriers", {}).get(
                    carrier_code, carrier_code or ""
                )

                dep_obj = segment.get("departure", {}) or {}
                arr_obj = segment.get("arrival", {}) or {}
                dep_code = dep_obj.get("iataCode", "")
                arr_code = arr_obj.get("iataCode", "")
                dep_at   = _fmt_time(dep_obj.get("at", ""))   # HH:MM
                arr_at   = _fmt_time(arr_obj.get("at", ""))   # HH:MM

                segments_list.append(
                    {
                        "carrier": carrier,
                        "route": f"{dep_code} → {arr_code}",
                        "dep_time": dep_at,
                        "arr_time": arr_at,
                    }
                )

        flights.append({"price": price, "segments": segments_list})

    if not flights:
        return None

    cheapest = min(flights, key=lambda x: x["price"])
    return cheapest


# ---- Location Resolver (city/airport/IATA) ----
def _search_amadeus_locations(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Call Amadeus Airport & City Search API.
    Cached by keyword. Returns list of normalized location dicts.
    """
    k = (keyword or "").strip().upper()
    if len(k) < _MIN_KEYWORD_LEN:
        return []

    # Check cache
    now = time.time()
    if k in _LOCATIONS_CACHE:
        cached_results, ts = _LOCATIONS_CACHE[k]
        if now - ts < _LOCATIONS_CACHE_TTL:
            return cached_results[:limit]

    try:
        token = get_access_token()
    except AmadeusError:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "subType": "AIRPORT,CITY",
        "keyword": k,
        "page[limit]": min(limit, 20),
    }
    try:
        resp = requests.get(LOCATIONS_URL, headers=headers, params=params, timeout=10)
    except requests.exceptions.Timeout:
        logger.warning("Amadeus locations API timeout for keyword=%s", k)
        return []
    except requests.exceptions.RequestException as e:
        logger.warning("Amadeus locations API request failed: %s", e)
        return []

    if resp.status_code != 200:
        if resp.status_code == 429:
            logger.warning("Amadeus locations API rate limit (429)")
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    raw = data.get("data") or []
    results: list[dict[str, Any]] = []
    seen_iata: set[str] = set()

    for loc in raw:
        iata = (loc.get("iataCode") or "").strip().upper()
        if not iata or len(iata) != 3 or iata in seen_iata:
            continue
        seen_iata.add(iata)
        addr = loc.get("address") or {}
        city = (addr.get("cityName") or loc.get("name") or "").strip()
        country = (addr.get("countryCode") or "").strip().upper()
        name = (loc.get("name") or "").strip()
        sub = (loc.get("subType") or "").upper()
        label = f"{city} ({iata})" if city else f"{name} ({iata})"
        results.append({
            "label": label,
            "city_name": city,
            "airport_name": name if sub == "AIRPORT" else "",
            "iata_code": iata,
            "country_code": country,
            "source": "api",
        })
        if len(results) >= limit:
            break

    _LOCATIONS_CACHE[k] = (results, now)
    return results


def resolve_to_iata(query: str) -> str | None:
    """
    Resolve user input (city, airport name, or IATA) to a single IATA code.
    Fallback order: normalize -> 3-letter IATA check -> local mapping -> Amadeus API.
    Returns IATA string or None if not found.
    """
    q = airport_data.normalize_input(query)
    if not q:
        return None

    # 1) Looks like IATA: check local first
    if airport_data.looks_like_iata(q):
        iata_local = airport_data.resolve_to_iata_local(q)
        if iata_local:
            return iata_local
        # Might be valid IATA not in our list; try Amadeus to validate
        api_results = _search_amadeus_locations(q, limit=1)
        if api_results:
            return (api_results[0].get("iata_code") or "").upper() or None
        # Return as-is if 3 letters (Amadeus flight-offers accepts it)
        return q.upper()

    # 2) Local mapping
    iata_local = airport_data.resolve_to_iata_local(q)
    if iata_local:
        return iata_local

    # 3) Amadeus API
    api_results = _search_amadeus_locations(q, limit=1)
    if api_results:
        return (api_results[0].get("iata_code") or "").upper() or None

    return None


def search_locations(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search locations for autocomplete.
    Returns list of {label, city_name, airport_name, iata_code, country_code, source}.
    Fallback: local first, then Amadeus API. Deduplicated by IATA.
    """
    q = airport_data.normalize_input(query)
    if not q:
        return []

    # Local first
    local_results = airport_data.search_local(q, limit=limit)
    seen = {r.get("iata_code") for r in local_results if r.get("iata_code")}
    out: list[dict[str, Any]] = []
    for r in local_results:
        out.append({**r, "source": r.get("source") or "local"})

    if len(out) >= limit:
        return out[:limit]

    # Amadeus for more
    api_results = _search_amadeus_locations(q, limit=limit - len(out))
    for r in api_results:
        code = r.get("iata_code")
        if code and code not in seen:
            seen.add(code)
            out.append(r)
            if len(out) >= limit:
                break

    return out[:limit]


def cheap_flight_locations_api(request):
    """
    JSON API for location autocomplete.
    GET params: q (min 2 chars), limit? (default 10)
    """
    q = (request.GET.get("q") or "").strip()
    try:
        limit = max(1, min(20, int(request.GET.get("limit") or 10)))
    except (ValueError, TypeError):
        limit = 10

    if len(q) < 2:
        return JsonResponse(
            {"success": True, "data": [], "errors": []},
        )

    results = search_locations(q, limit=limit)
    # Ensure label format: "City (IATA)" or "Airport (IATA)"
    out = []
    for r in results:
        label = r.get("label") or ""
        if not label and r.get("iata_code"):
            city = r.get("city_name") or ""
            airport = r.get("airport_name") or ""
            label = f"{city or airport} ({r['iata_code']})" if (city or airport) else r["iata_code"]
        out.append({
            "label": label or "",
            "city_name": r.get("city_name") or "",
            "airport_name": r.get("airport_name") or "",
            "iata_code": r.get("iata_code") or "",
            "country_code": r.get("country_code") or "",
            "source": r.get("source") or "local",
        })

    return JsonResponse(
        {"success": True, "data": out, "errors": []},
    )


def _deduplicate_flights(flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove duplicates: same route, same departure datetime, same price.
    Keeps first occurrence.
    """
    seen: set[tuple[str, str, float]] = set()
    out: list[dict[str, Any]] = []
    for f in flights:
        route = f.get("route_display") or f"{f.get('departure_iata')}-{f.get('arrival_iata')}"
        dep = f.get("departure_datetime") or ""
        price = float(f.get("price") or 0)
        key = (route, dep[:19] if dep else "", round(price, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def cheap_flight_search_api(request):
    """
    JSON API for flight search. Returns normalized flights, filter-ready.
    GET params: origin, destination, depart_date, return_date?, currency?, trip_type?, adults?
    """
    start_ms = time.time() * 1000
    errors: list[str] = []
    warnings: list[str] = []

    origin_query = (request.GET.get("origin") or "").strip()
    destination_query = (request.GET.get("destination") or "").strip()
    depart_date = (request.GET.get("depart_date") or "").strip()
    return_date = (request.GET.get("return_date") or "").strip()
    currency = (request.GET.get("currency") or "USD").upper().strip()
    trip_type = (request.GET.get("trip_type") or "one_way").strip().lower()
    try:
        adults = max(1, min(9, int(request.GET.get("adults") or 1)))
    except (ValueError, TypeError):
        adults = 1

    # Validation
    if not origin_query:
        errors.append("invalid origin")
    if not destination_query:
        errors.append("invalid destination")
    if not depart_date:
        errors.append("missing date")
    elif len(depart_date) < 10:
        errors.append("invalid depart_date format (use YYYY-MM-DD)")
    if trip_type == "round_trip" and not return_date:
        errors.append("return_date required for round trip")

    # Date validation: return must be >= departure for round trip
    if trip_type == "round_trip" and depart_date and return_date and len(depart_date) >= 10 and len(return_date) >= 10:
        try:
            from datetime import datetime

            d_dep = datetime.strptime(depart_date[:10], "%Y-%m-%d")
            d_ret = datetime.strptime(return_date[:10], "%Y-%m-%d")
            if d_ret < d_dep:
                errors.append("return_date cannot be before depart_date")
        except (ValueError, TypeError):
            pass

    if errors:
        return JsonResponse(
            {
                "success": False,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                },
                "data": [],
                "warnings": [],
                "errors": errors,
            },
            status=400,
        )

    # Resolve origin/destination
    origin_iata = resolve_to_iata(origin_query)
    destination_iata = resolve_to_iata(destination_query)

    if not origin_iata:
        return JsonResponse(
            {
                "success": False,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "origin_iata": None,
                    "destination_iata": destination_iata,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                },
                "data": [],
                "warnings": [],
                "errors": ["invalid origin"],
            },
            status=400,
        )

    if not destination_iata:
        return JsonResponse(
            {
                "success": False,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "origin_iata": origin_iata,
                    "destination_iata": None,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                },
                "data": [],
                "warnings": [],
                "errors": ["invalid destination"],
            },
            status=400,
        )

    # Amadeus call
    try:
        rd = return_date if trip_type == "round_trip" else None
        payload = get_offers(
            origin=origin_iata,
            destination=destination_iata,
            depart_date=depart_date,
            currency=currency,
            max_items=15,
            return_date=rd,
            adults=adults,
        )
    except AmadeusError as e:
        err_str = str(e).lower()
        if "429" in err_str or "rate" in err_str or "quota" in err_str:
            return JsonResponse(
                {
                    "success": False,
                    "meta": {
                        "origin_query": origin_query,
                        "destination_query": destination_query,
                        "origin_iata": origin_iata,
                        "destination_iata": destination_iata,
                        "trip_type": trip_type,
                        "currency": currency,
                        "result_count": 0,
                        "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                    },
                    "data": [],
                    "warnings": [],
                    "errors": ["rate limited"],
                },
                status=429,
            )
        return JsonResponse(
            {
                "success": False,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                },
                "data": [],
                "warnings": [],
                "errors": ["api temporarily unavailable"],
            },
            status=503,
        )
    except requests.exceptions.Timeout:
        return JsonResponse(
            {
                "success": False,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                },
                "data": [],
                "warnings": [],
                "errors": ["api temporarily unavailable"],
            },
            status=503,
        )
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.exception("Flight search API error: %s", e)
        return JsonResponse(
            {
                "success": False,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": round((time.time() * 1000) - start_ms, 0),
                },
                "data": [],
                "warnings": [],
                "errors": ["api temporarily unavailable"],
            },
            status=503,
        )

    # Normalize
    raw_data = payload.get("data") or []
    if not raw_data:
        search_ms = round((time.time() * 1000) - start_ms, 0)
        return JsonResponse(
            {
                "success": True,
                "meta": {
                    "origin_query": origin_query,
                    "destination_query": destination_query,
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "trip_type": trip_type,
                    "currency": currency,
                    "result_count": 0,
                    "search_time_ms": search_ms,
                },
                "data": [],
                "warnings": warnings,
                "errors": [],
            },
        )

    flights = normalize_all_offers(
        payload,
        reference_depart_date=depart_date,
        include_raw=False,
    )
    flights = _deduplicate_flights(flights)
    flights = apply_badges(flights)
    flights.sort(key=lambda x: (float(x.get("price") or 0), x.get("total_minutes") or 0))
    flights = flights[:10]

    if len(raw_data) > 10:
        warnings.append("Some results may be limited due to API constraints.")

    search_ms = round((time.time() * 1000) - start_ms, 0)

    # Resolve destination to city name and country
    destination_city = ""
    destination_country = ""
    if destination_iata:
        destination_city = airport_data.iata_to_city(destination_iata)
        destination_country = airport_data.iata_to_country(destination_iata)
    if not destination_city and destination_query and not airport_data.looks_like_iata(destination_query):
        destination_city = destination_query.strip()
    elif not destination_city:
        destination_city = destination_iata or ""

    return JsonResponse(
        {
            "success": True,
            "meta": {
                "origin_query": origin_query,
                "destination_query": destination_query,
                "origin_iata": origin_iata,
                "destination_iata": destination_iata,
                "destination_city": destination_city,
                "destination_country": destination_country,
                "depart_date": depart_date,
                "return_date": return_date,
                "trip_type": trip_type,
                "currency": currency,
                "result_count": len(flights),
                "search_time_ms": search_ms,
            },
            "data": flights,
            "warnings": warnings,
            "errors": [],
        },
    )


# ---- API: store / restore flight context (auth flow) ----
def _flight_context_valid(ts: float) -> bool:
    return ts and (time.time() - float(ts)) < CFF_SESSION_MAX_AGE


@require_POST
def store_flight_context_api(request):
    """Store selected flight in session before redirecting to login."""
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    flight = body.get("flight")
    if not flight or not isinstance(flight, dict):
        return JsonResponse({"success": False, "error": "Missing flight data"}, status=400)
    # Temporary payload for restore + email (no DB save; session only)
    f = flight
    origin = str(f.get("origin") or f.get("departure_iata", ""))
    dest = str(f.get("destination") or f.get("outbound_arrival_iata") or f.get("arrival_iata", ""))
    segs = f.get("segments") or (f.get("outbound") or {}).get("segments", [])
    fn = ""
    if segs and isinstance(segs, list) and len(segs) > 0:
        s0 = segs[0] or {}
        fn = f"{s0.get('carrier_code', '')} {s0.get('number', '')}".strip()
    payload = {
        "flight": {
            "id": str(f.get("id", "")),
            "origin": origin,
            "destination": dest,
            "depart_date": str(f.get("depart_date") or f.get("departure_date", "")),
            "return_date": str(f.get("return_date") or ""),
            "price": f.get("price"),
            "currency": str(f.get("currency", "USD")),
            "duration_minutes": f.get("duration_minutes") or f.get("total_minutes"),
            "stops": f.get("stops"),
            "airline": str(f.get("airline") or f.get("primary_airline", "")),
            "depart_time": str(f.get("depart_time") or f.get("departure_time", "")),
            "arrival_time": str(f.get("arrival_time", "")),
            "route_display": str(f.get("route_display", "") or (f"{origin} → {dest}" if origin or dest else "")),
            "price_display": str(f.get("price_display", "")),
            "primary_airline": str(f.get("primary_airline") or f.get("airline", "")),
            "stop_label": str(f.get("stop_label", "")),
            "total_duration": str(f.get("total_duration", "")),
            "departure_date": str(f.get("departure_date") or f.get("depart_date", "")),
            "departure_time": str(f.get("departure_time") or f.get("depart_time", "")),
            "arrival_date": str(f.get("arrival_date", "")),
            "departure_iata": origin,
            "arrival_iata": dest,
            "outbound_arrival_iata": dest,
            "flight_number": fn or str(f.get("flight_number", "")),
            "segments": segs[:3] if segs else [],
        },
        "ts": time.time(),
    }
    request.session[CFF_SESSION_KEY] = payload
    request.session.modified = True
    return JsonResponse({"success": True})


@require_GET
def restore_flight_context_api(request):
    """Return stored flight and clear session. Used after login redirect."""
    data = request.session.get(CFF_SESSION_KEY)
    if not data:
        return JsonResponse({"success": True, "flight": None})
    ts = data.get("ts")
    if not _flight_context_valid(ts):
        del request.session[CFF_SESSION_KEY]
        return JsonResponse({"success": True, "flight": None})
    flight = data.get("flight")
    del request.session[CFF_SESSION_KEY]
    request.session.modified = True
    return JsonResponse({"success": True, "flight": flight})


@require_POST
def send_sms_api(request):
    """Send flight details via SMS. Requires auth; uses session-stored or provided flight."""
    from main.flight_services import send_flight_sms

    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Login required"}, status=401)
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    phone = (body.get("phone") or "").strip()
    flight = body.get("flight")
    if not flight:
        flight = request.session.get(CFF_SESSION_KEY, {}).get("flight")
    if not flight or not isinstance(flight, dict):
        return JsonResponse({"success": False, "error": "No flight selected"}, status=400)
    result = send_flight_sms(phone, flight)
    if result.get("success"):
        return JsonResponse({"success": True, "message": "Flight details sent"})
    return JsonResponse({"success": False, "error": result.get("error", "Unable to send")}, status=400)


@require_POST
def send_email_api(request):
    """Send flight details via email. Uses same infrastructure as registration (accounts.email.service)."""
    from accounts.email.service import send_flight_details
    from main.flight_services import _normalize_flight_for_display

    logger.info("[CFF] send_email_api called, auth=%s", request.user.is_authenticated)

    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Login required"}, status=401)
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    to_email = (body.get("email") or "").strip()
    if not to_email and request.user.is_authenticated:
        to_email = (request.user.email or "").strip()
        if not to_email:
            try:
                from allauth.account.models import EmailAddress
                primary = EmailAddress.objects.get_primary(request.user)
                if primary:
                    to_email = (primary.email or "").strip()
            except Exception:
                pass
    flight = body.get("flight")
    if not flight:
        flight = request.session.get(CFF_SESSION_KEY, {}).get("flight")
    if not flight or not isinstance(flight, dict):
        return JsonResponse({"success": False, "error": "No flight selected"}, status=400)
    if not to_email:
        return JsonResponse(
            {"success": False, "error": "Your account has no email. Please add an email in your profile."},
            status=400,
        )
    flight_ctx = {**flight, **_normalize_flight_for_display(flight)}
    ok = send_flight_details(to_email=to_email, flight_ctx=flight_ctx)
    if ok:
        logger.info("Flight email sent to %s", to_email)
        return JsonResponse({"success": True, "message": "Flight details sent"})
    logger.warning("Flight email send returned False (to=%s)", to_email)
    return JsonResponse({"success": False, "error": "Unable to send email right now"}, status=400)


@require_GET
def city_guide_api(request):
    """City guide for AI tab. Optional: city, country, depart_date, return_date."""
    from main.city_guide import get_city_guide

    city = (request.GET.get("city") or "").strip()
    country = (request.GET.get("country") or "").strip()
    depart_date = (request.GET.get("depart_date") or "").strip()
    return_date = (request.GET.get("return_date") or "").strip()
    if not city:
        return JsonResponse({"success": False, "error": "city required"}, status=400)
    result = get_city_guide(city=city, country=country, depart_date=depart_date, return_date=return_date)
    if not result.get("success"):
        return JsonResponse(
            {"success": False, "error": result.get("error", "City guide unavailable")},
            status=400 if result.get("error") else 500,
        )
    return JsonResponse({"success": True, "data": result.get("data", {})})


GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
# Places API (New) - legacy API returns REQUEST_DENIED for new projects
PLACES_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = "places.id,places.displayName,places.rating,places.userRatingCount,places.priceLevel,places.priceRange,places.formattedAddress,places.photos,places.googleMapsUri"

_PRICE_MAP = {
    "PRICE_LEVEL_FREE": "",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
}


def _places_search_text(query: str) -> dict | None:
    """Call Places API (New) text search. Returns JSON or None."""
    if not query or not GOOGLE_PLACES_API_KEY:
        return None
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK,
    }
    resp = requests.post(
        PLACES_SEARCH_TEXT_URL,
        headers=headers,
        json={"textQuery": query},
        timeout=10,
    )
    if resp.status_code != 200:
        logger.warning("Places searchText status=%s body=%s", resp.status_code, resp.text[:200])
        return None
    return resp.json()


@require_GET
def place_photo_api(request):
    """
    Proxy for Google Places photos (Places API New). GET ?query=Restaurant+Warsaw
    Returns image bytes or 204 if unavailable.
    """
    query = (request.GET.get("query") or "").strip()
    if not query or not GOOGLE_PLACES_API_KEY:
        return HttpResponse(status=204)

    try:
        data = _places_search_text(query)
        if not data:
            return HttpResponse(status=204)
        places = data.get("places") or []
        if not places:
            return HttpResponse(status=204)
        photos = (places[0].get("photos") or [])[:1]
        if not photos:
            return HttpResponse(status=204)
        photo_name = photos[0].get("name")
        if not photo_name or "/media" in photo_name:
            return HttpResponse(status=204)
        # Photo media: https://places.googleapis.com/v1/places/PHOTO_NAME/media?maxWidthPx=800&key=API_KEY
        media_name = photo_name.rstrip("/") + "/media"
        url = f"https://places.googleapis.com/v1/{media_name}"
        img_resp = requests.get(
            url,
            params={"maxWidthPx": 800, "key": GOOGLE_PLACES_API_KEY},
            timeout=10,
            allow_redirects=True,
        )
        if img_resp.status_code != 200:
            return HttpResponse(status=204)
        ct = img_resp.headers.get("Content-Type") or "image/jpeg"
        return HttpResponse(img_resp.content, content_type=ct)
    except Exception:
        logger.exception("Place photo fetch failed for query=%s", query[:50])
        return HttpResponse(status=204)


@require_GET
def place_details_api(request):
    """
    Google Places details (Places API New). GET ?query=Hotel+Name+City
    Returns JSON: { name, rating, price_level, photo_url, maps_url }
    """
    query = (request.GET.get("query") or "").strip()
    if not query or not GOOGLE_PLACES_API_KEY:
        return JsonResponse({"success": False, "error": "Missing query or API key"}, status=400)

    try:
        data = _places_search_text(query)
        if not data:
            return JsonResponse({"success": False, "error": "Search failed"}, status=500)
        places = data.get("places") or []
        if not places:
            return JsonResponse({"success": True, "data": None})

        place = places[0]
        display_name = place.get("displayName") or {}
        name = display_name.get("text", "") if isinstance(display_name, dict) else str(display_name or "")
        rating = place.get("rating")
        user_ratings_total = place.get("userRatingCount")
        price_level_raw = place.get("priceLevel")
        price_range = place.get("priceRange")  # may have formattedPrice or similar
        formatted_address = place.get("formattedAddress")
        photos = (place.get("photos") or [])[:1]
        photo_name = photos[0].get("name") if photos else None
        google_maps_uri = place.get("googleMapsUri")
        place_id = place.get("id", "").replace("places/", "") if place.get("id") else None

        maps_url = google_maps_uri or f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(name + ' ' + query)}"
        if place_id and not google_maps_uri:
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

        photo_url = None
        if photo_name:
            photo_url = f"/cheap-flight-finder/api/place-photo/?query={requests.utils.quote(query)}"

        price_str = _PRICE_MAP.get(price_level_raw, "") if isinstance(price_level_raw, str) else ""

        # priceRange: { startPrice: {currencyCode, units, nanos}, endPrice: {...} }
        def _fmt_money(m: dict) -> str:
            if not isinstance(m, dict):
                return ""
            cc = m.get("currencyCode") or "USD"
            sym = "$" if cc == "USD" else (cc + " ")
            u = m.get("units") or "0"
            try:
                n = int(m.get("nanos") or 0)
                if n:
                    return f"{sym}{int(u)}.{str(n).zfill(9).rstrip('0')}"
                return f"{sym}{int(u)}"
            except (ValueError, TypeError):
                return f"{sym}{u}"

        if isinstance(price_range, dict) and price_range:
            start = _fmt_money(price_range.get("startPrice") or {})
            end = _fmt_money(price_range.get("endPrice") or {})
            if start and end:
                price_str = f"{start} – {end}"
            elif start:
                price_str = price_str or f"From {start}"

        out = {
            "name": name,
            "rating": round(float(rating), 1) if rating is not None else None,
            "user_ratings_total": user_ratings_total,
            "price_level": price_level_raw,
            "price_display": price_str,
            "formatted_address": formatted_address or "",
            "photo_url": photo_url,
            "maps_url": maps_url,
        }
        return JsonResponse({"success": True, "data": out})
    except Exception as e:
        logger.exception("Place details failed for query=%s", query[:50])
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ---- Django VIEW (views.py-sız) ----
@ensure_csrf_cookie
def cheap_flight_finder_view(request):
    origin = (request.GET.get("origin") or "").upper().strip()
    destination = (request.GET.get("destination") or "").upper().strip()
    depart_date = (request.GET.get("depart_date") or "").strip()  # YYYY-MM-DD
    currency = (request.GET.get("currency") or "USD").upper().strip()

    error = None
    result = None  # {"price": 123.45, "currency": "USD", "segments": [...]}
    sample_rows = []

    if origin and destination and depart_date:
        # Resolve city/airport names to IATA if needed (keeps existing IATA flow)
        origin_iata = origin if airport_data.looks_like_iata(origin) else (resolve_to_iata(origin) or origin)
        dest_iata = destination if airport_data.looks_like_iata(destination) else (resolve_to_iata(destination) or destination)
        try:
            offers = get_offers(origin_iata, dest_iata, depart_date, currency)
            cheapest = pick_cheapest(offers)
            if not cheapest:
                error = "No offers found for the given inputs."
            else:
                result = {
                    "price": cheapest["price"],
                    "currency": currency,
                    "segments": cheapest["segments"],
                }
                # UI üçün kiçik kontekst (bir neçə nümunə segment)
                for offer in offers.get("data", [])[:3]:
                    for itin in offer.get("itineraries", [])[:1]:
                        for seg in itin.get("segments", [])[:2]:
                            carrier = offers.get("dictionaries", {}).get("carriers", {}).get(
                                seg.get("carrierCode"),
                                seg.get("carrierCode"),
                            )
                            dep = seg.get("departure", {}) or {}
                            arr = seg.get("arrival", {}) or {}
                            sample_rows.append(
                                {
                                    "carrier": carrier,
                                    "from": dep.get("iataCode"),
                                    "to": arr.get("iataCode"),
                                    "dep_time": _fmt_time(dep.get("at", "")),
                                    "arr_time": _fmt_time(arr.get("at", "")),
                                }
                            )
        except AmadeusError as e:
            error = str(e)
        except Exception as e:
            error = f"Unexpected error: {e}"

    login_url = "/auth/login/"
    next_url = "/cheap-flight-finder/"
    return render(
        request,
        "cheap_flight_finder.html",
        {
            "origin": origin,
            "destination": destination,
            "depart_date": depart_date,
            "currency": currency,
            "result": result,
            "error": error,
            "sample_rows": sample_rows,
            "user_is_authenticated": request.user.is_authenticated,
            "login_url": login_url,
            "next_url": next_url,
        },
    )
