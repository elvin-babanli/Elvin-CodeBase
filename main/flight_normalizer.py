"""
Flight offer normalization: Amadeus raw response -> stable normalized model.
Null-safe, defensive parsing. Supports one-way and round-trip.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso8601_duration_to_minutes(dur: str | None) -> int | None:
    """
    PT2H30M -> 150, PT1H -> 60, P1D -> 1440.
    Returns None if invalid or empty.
    """
    if not dur or not isinstance(dur, str):
        return None
    s = dur.strip().upper()
    if not s.startswith("P"):
        return None
    total = 0
    # PT2H30M: T 이후 H, M, S
    m = re.match(r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)(?:[.,]\d+)?S)?)?$", s)
    if m:
        y, mo, d, h, mi, sec = m.groups()
        total = (int(y or 0) * 365 * 24 * 60 +
                 int(mo or 0) * 30 * 24 * 60 +
                 int(d or 0) * 24 * 60 +
                 int(h or 0) * 60 +
                 int(mi or 0) +
                 int(float(sec or 0)))
        return total
    return None


def _format_duration_minutes(minutes: int | None) -> str:
    """150 -> '2h 30m'"""
    if minutes is None or minutes < 0:
        return ""
    h = minutes // 60
    m = minutes % 60
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return s if s else ""


def _parse_datetime_iso(iso_str: str | None) -> tuple[str, str, str] | None:
    """
    '2025-06-15T14:30:00' -> (date, time, full).
    Returns (date_str, time_str, datetime_str) or None.
    """
    if not iso_str or "T" not in str(iso_str):
        return None
    try:
        parts = str(iso_str).split("T", 1)
        date_part = parts[0][:10]
        time_part = (parts[1][:8] if len(parts) > 1 else "")[:5]  # HH:MM
        return (date_part, time_part, str(iso_str)[:19])
    except Exception:
        return None


def _get_city_for_iata(iata: str) -> str:
    """Optional: map IATA to city name via airport_data."""
    try:
        from main import airport_data
        results = airport_data.search_local(iata, limit=1)
        if results and results[0].get("city_name"):
            return results[0]["city_name"]
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Segment normalization
# ---------------------------------------------------------------------------


def _normalize_segment(seg: dict[str, Any], carriers: dict[str, str]) -> dict[str, Any]:
    dep = seg.get("departure") or {}
    arr = seg.get("arrival") or {}
    dep_at = dep.get("at") or ""
    arr_at = arr.get("at") or ""
    dep_parsed = _parse_datetime_iso(dep_at)
    arr_parsed = _parse_datetime_iso(arr_at)

    carrier_code = _safe_str(seg.get("carrierCode") or seg.get("operating", {}).get("carrierCode")).upper()
    aircraft = seg.get("aircraft") or {}
    aircraft_code = _safe_str(aircraft.get("code"))

    dur_str = seg.get("duration") or ""
    dur_min = _parse_iso8601_duration_to_minutes(dur_str)

    return {
        "departure_iata": _safe_str(dep.get("iataCode")).upper() or "",
        "arrival_iata": _safe_str(arr.get("iataCode")).upper() or "",
        "departure_at": dep_at,
        "arrival_at": arr_at,
        "departure_date": dep_parsed[0] if dep_parsed else "",
        "departure_time": dep_parsed[1] if dep_parsed else "",
        "arrival_date": arr_parsed[0] if arr_parsed else "",
        "arrival_time": arr_parsed[1] if arr_parsed else "",
        "carrier_code": carrier_code,
        "carrier_name": carriers.get(carrier_code) or carrier_code,
        "number": _safe_str(seg.get("number")),
        "aircraft_code": aircraft_code,
        "duration": _format_duration_minutes(dur_min),
        "duration_minutes": dur_min,
        "departure_terminal": _safe_str(dep.get("terminal")),
        "arrival_terminal": _safe_str(arr.get("terminal")),
    }


# ---------------------------------------------------------------------------
# Main normalization
# ---------------------------------------------------------------------------


def normalize_flight_offer(
    offer: dict[str, Any],
    dictionaries: dict[str, Any] | None = None,
    reference_depart_date: str | None = None,
    include_raw: bool = False,
) -> dict[str, Any] | None:
    """
    Convert a single Amadeus flight offer to normalized format.
    Returns None if offer is invalid (e.g. no price).
    """
    if not offer or not isinstance(offer, dict):
        return None

    carriers = {}
    locations = {}
    if dictionaries:
        carriers = (dictionaries.get("carriers") or {}) or {}
        locations = (dictionaries.get("locations") or {}) or {}

    # Price
    price_obj = offer.get("price") or {}
    total_raw = price_obj.get("total") or price_obj.get("grandTotal")
    price = _safe_float(total_raw)
    if price is None:
        return None
    currency = _safe_str(price_obj.get("currency")).upper() or "USD"

    # Id
    offer_id = _safe_str(offer.get("id"))

    # Itineraries: first = outbound, second = return
    itineraries = offer.get("itineraries") or []
    if not itineraries:
        return None

    outbound_segments: list[dict[str, Any]] = []
    return_segments: list[dict[str, Any]] = []
    total_minutes = 0
    first_dep_datetime = ""
    first_dep_date = ""
    last_arr_datetime = ""
    last_arr_date = ""
    airline_codes_set: set[str] = set()

    for idx, itin in enumerate(itineraries):
        segs = itin.get("segments") or []
        itin_dur = _parse_iso8601_duration_to_minutes(itin.get("duration"))
        if itin_dur is not None:
            total_minutes += itin_dur

        for seg in segs:
            ns = _normalize_segment(seg, carriers)
            if ns.get("carrier_code"):
                airline_codes_set.add(ns["carrier_code"])
            if idx == 0:
                outbound_segments.append(ns)
            else:
                return_segments.append(ns)

    if outbound_segments:
        first_dep_datetime = outbound_segments[0].get("departure_at", "")
        first_dep_date = outbound_segments[0].get("departure_date", "")
        last_out = outbound_segments[-1]
        last_arr_datetime = last_out.get("arrival_at", "")
        last_arr_date = last_out.get("arrival_date", "")
    if return_segments:
        last_ret = return_segments[-1]
        last_arr_datetime = last_ret.get("arrival_at", "")
        last_arr_date = last_ret.get("arrival_date", "")

    # Departure / arrival from first/last segment
    dep_iata = outbound_segments[0].get("departure_iata", "") if outbound_segments else ""
    if return_segments:
        arr_iata = return_segments[-1].get("arrival_iata", "")
    else:
        arr_iata = outbound_segments[-1].get("arrival_iata", "") if outbound_segments else ""

    dep_city = _get_city_for_iata(dep_iata) if dep_iata else ""
    arr_city = _get_city_for_iata(arr_iata) if arr_iata else ""

    # Locations dict: Amadeus may have locations[IATA] = {cityCode}
    if dep_iata and not dep_city:
        loc = locations.get(dep_iata) or {}
        dep_city = _safe_str(loc.get("cityCode")) or dep_iata
    if arr_iata and not arr_city:
        loc = locations.get(arr_iata) or {}
        arr_city = _safe_str(loc.get("cityCode")) or arr_iata

    # Stops
    total_segments = len(outbound_segments) + len(return_segments)
    stops = max(0, total_segments - (2 if return_segments else 1))
    is_direct = stops == 0
    if stops == 0:
        stop_label = "Direct"
    elif stops == 1:
        stop_label = "1 stop"
    else:
        stop_label = f"{stops} stops"

    # Next day arrival
    next_day_arrival = False
    if first_dep_date and last_arr_date and first_dep_date != last_arr_date:
        next_day_arrival = True

    # Days left
    days_left: int | None = None
    if reference_depart_date or first_dep_date:
        ref = reference_depart_date or first_dep_date
        try:
            dep_d = datetime.strptime(ref[:10], "%Y-%m-%d").date()
            days_left = (dep_d - date.today()).days
        except (ValueError, TypeError):
            pass

    # Cabin / baggage from travelerPricings
    cabin = ""
    baggage = ""
    try:
        tp = (offer.get("travelerPricings") or [])
        if tp:
            fds = (tp[0].get("fareDetailsBySegment") or [])
            if fds:
                cabin = _safe_str(fds[0].get("cabin"))
            # Baggage: check fareDetailsBySegment includedCheckedBags
            for fd in fds:
                bags = fd.get("includedCheckedBags") or {}
                if isinstance(bags, dict) and bags.get("quantity") is not None:
                    qty = bags.get("quantity", 0)
                    baggage = f"{qty} checked" if qty else ""
                    break
    except Exception:
        pass

    # Validating airline codes
    val_codes = offer.get("validatingAirlineCodes") or []
    validating_airline_codes = [x for x in val_codes if x] if isinstance(val_codes, list) else []

    # Primary airline
    primary_airline = ""
    if validating_airline_codes:
        pc = validating_airline_codes[0]
        primary_airline = carriers.get(pc) or pc
    elif airline_codes_set:
        primary_airline = carriers.get(next(iter(airline_codes_set))) or next(iter(airline_codes_set))

    # Outbound / return_leg
    outbound = {
        "segments": outbound_segments,
        "duration_minutes": sum(s.get("duration_minutes") or 0 for s in outbound_segments),
    }
    outbound["duration"] = _format_duration_minutes(outbound["duration_minutes"])

    return_leg: dict[str, Any] | None = None
    if return_segments:
        return_leg = {
            "segments": return_segments,
            "duration_minutes": sum(s.get("duration_minutes") or 0 for s in return_segments),
        }
        return_leg["duration"] = _format_duration_minutes(return_leg["duration_minutes"])

    trip_type = "round_trip" if return_segments else "one_way"

    # Route display: always show outbound (origin → destination), not overall return arrival
    outbound_arr_iata = outbound_segments[-1].get("arrival_iata", "") if outbound_segments else ""
    route_display = f"{dep_iata} → {outbound_arr_iata}" if dep_iata and outbound_arr_iata else ""
    price_display = f"{price:.2f} {currency}" if price is not None else ""

    # Outbound destination (for session/store when round-trip)
    result_outbound_arr_iata = outbound_arr_iata

    result: dict[str, Any] = {
        "id": offer_id,
        "price": price,
        "currency": currency,
        "total_duration": _format_duration_minutes(total_minutes),
        "total_minutes": total_minutes,
        "stops": stops,
        "stop_label": stop_label,
        "is_direct": is_direct,
        "airline_codes": list(airline_codes_set),
        "airline_names": [carriers.get(c) or c for c in airline_codes_set],
        "primary_airline": primary_airline,
        "departure_city": dep_city,
        "departure_airport": dep_iata,
        "departure_iata": dep_iata,
        "departure_terminal": outbound_segments[0].get("departure_terminal", "") if outbound_segments else "",
        "departure_datetime": first_dep_datetime,
        "departure_date": first_dep_date,
        "departure_time": outbound_segments[0].get("departure_time", "") if outbound_segments else "",
        "arrival_city": arr_city,
        "arrival_airport": arr_iata,
        "arrival_iata": arr_iata,
        "arrival_terminal": (
            (return_segments[-1] if return_segments else outbound_segments[-1]).get("arrival_terminal", "")
        ) if outbound_segments or return_segments else "",
        "arrival_datetime": last_arr_datetime,
        "arrival_date": last_arr_date,
        "arrival_time": (
            (return_segments[-1] if return_segments else outbound_segments[-1]).get("arrival_time", "")
        ) if outbound_segments or return_segments else "",
        "next_day_arrival": next_day_arrival,
        "days_left": days_left,
        "segments": outbound_segments + return_segments,
        "outbound": outbound,
        "return_leg": return_leg,
        "trip_type": trip_type,
        "cabin": cabin,
        "baggage": baggage,
        "validating_airline_codes": validating_airline_codes,
        "booking_classes": [],
        "badges": [],
        "route_display": route_display,
        "price_display": price_display,
        "outbound_arrival_iata": result_outbound_arr_iata,
    }

    if include_raw:
        result["raw_offer"] = offer

    return result


def normalize_all_offers(
    payload: dict[str, Any],
    reference_depart_date: str | None = None,
    include_raw: bool = False,
) -> list[dict[str, Any]]:
    """
    Normalize all offers from Amadeus flight-offers response.
    Returns list of normalized offers, skips invalid ones.
    """
    if not payload or not isinstance(payload, dict):
        return []

    data = payload.get("data") or []
    dictionaries = payload.get("dictionaries") or {}

    results: list[dict[str, Any]] = []
    for offer in data:
        norm = normalize_flight_offer(
            offer,
            dictionaries=dictionaries,
            reference_depart_date=reference_depart_date,
            include_raw=include_raw,
        )
        if norm:
            results.append(norm)

    return results


def apply_badges(flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Add badges: cheapest, shortest, best_value (placeholder).
    Mutates each flight's badges list.
    """
    if not flights:
        return flights

    # Cheapest
    min_price = min((f.get("price") or float("inf")) for f in flights)
    for f in flights:
        if (f.get("price") or 0) == min_price:
            f.setdefault("badges", []).append("cheapest")

    # Shortest (lowest total_minutes)
    valid_mins = [f.get("total_minutes") for f in flights if f.get("total_minutes") is not None]
    if valid_mins:
        min_mins = min(valid_mins)
        for f in flights:
            if f.get("total_minutes") == min_mins:
                badges = f.setdefault("badges", [])
                if "shortest" not in badges:
                    badges.append("shortest")

    # Best value: cheapest among shortest-duration flights (placeholder)
    shortest_flights = [f for f in flights if "shortest" in (f.get("badges") or [])]
    if shortest_flights:
        best_val_price = min((f.get("price") or float("inf")) for f in shortest_flights)
        for f in shortest_flights:
            if (f.get("price") or 0) == best_val_price:
                badges = f.setdefault("badges", [])
                if "best_value" not in badges:
                    badges.append("best_value")

    return flights
