"""
Location resolver: city/airport/IATA mapping.
Static data + local lookup. No external API calls.
Used by location_resolver for the first fallback layer.
"""
from __future__ import annotations

import re
import unicodedata
from typing import TypedDict

# ---------------------------------------------------------------------------
# Normalized location output format
# ---------------------------------------------------------------------------


class LocationResult(TypedDict, total=False):
    label: str
    city_name: str
    airport_name: str
    iata_code: str
    country_code: str
    country_name: str
    source: str  # "iata" | "local" | "api"


# ---------------------------------------------------------------------------
# Popular locations: IATA, city, airport name, country
# Amadeus test env: US, Spain, UK, Germany, India. Plus Warsaw, Baku, etc.
# ---------------------------------------------------------------------------

POPULAR_LOCATIONS = [
    # Europe
    {"iata": "WAW", "city": "Warsaw", "airport": "Chopin", "country": "PL", "country_name": "Poland"},
    {"iata": "GYD", "city": "Baku", "airport": "Heydar Aliyev", "country": "AZ", "country_name": "Azerbaijan"},
    {"iata": "IST", "city": "Istanbul", "airport": "Istanbul", "country": "TR", "country_name": "Turkey"},
    {"iata": "SAW", "city": "Istanbul", "airport": "Sabiha Gokcen", "country": "TR", "country_name": "Turkey"},
    {"iata": "BCN", "city": "Barcelona", "airport": "El Prat", "country": "ES", "country_name": "Spain"},
    {"iata": "MAD", "city": "Madrid", "airport": "Barajas", "country": "ES", "country_name": "Spain"},
    {"iata": "LHR", "city": "London", "airport": "Heathrow", "country": "GB", "country_name": "United Kingdom"},
    {"iata": "LGW", "city": "London", "airport": "Gatwick", "country": "GB", "country_name": "United Kingdom"},
    {"iata": "STN", "city": "London", "airport": "Stansted", "country": "GB", "country_name": "United Kingdom"},
    {"iata": "CDG", "city": "Paris", "airport": "Charles de Gaulle", "country": "FR", "country_name": "France"},
    {"iata": "ORY", "city": "Paris", "airport": "Orly", "country": "FR", "country_name": "France"},
    {"iata": "FRA", "city": "Frankfurt", "airport": "Frankfurt", "country": "DE", "country_name": "Germany"},
    {"iata": "MUC", "city": "Munich", "airport": "Munich", "country": "DE", "country_name": "Germany"},
    {"iata": "TXL", "city": "Berlin", "airport": "Tegel", "country": "DE", "country_name": "Germany"},
    {"iata": "BER", "city": "Berlin", "airport": "Brandenburg", "country": "DE", "country_name": "Germany"},
    {"iata": "AMS", "city": "Amsterdam", "airport": "Schiphol", "country": "NL", "country_name": "Netherlands"},
    {"iata": "VIE", "city": "Vienna", "airport": "Vienna", "country": "AT", "country_name": "Austria"},
    {"iata": "ZRH", "city": "Zurich", "airport": "Zurich", "country": "CH", "country_name": "Switzerland"},
    {"iata": "CPH", "city": "Copenhagen", "airport": "Copenhagen", "country": "DK", "country_name": "Denmark"},
    {"iata": "OSL", "city": "Oslo", "airport": "Gardermoen", "country": "NO", "country_name": "Norway"},
    {"iata": "ARN", "city": "Stockholm", "airport": "Arlanda", "country": "SE", "country_name": "Sweden"},
    {"iata": "HEL", "city": "Helsinki", "airport": "Helsinki", "country": "FI", "country_name": "Finland"},
    {"iata": "DUB", "city": "Dublin", "airport": "Dublin", "country": "IE", "country_name": "Ireland"},
    {"iata": "LIS", "city": "Lisbon", "airport": "Lisbon", "country": "PT", "country_name": "Portugal"},
    {"iata": "ATH", "city": "Athens", "airport": "Athens", "country": "GR", "country_name": "Greece"},
    {"iata": "PRG", "city": "Prague", "airport": "Prague", "country": "CZ", "country_name": "Czech Republic"},
    {"iata": "BUD", "city": "Budapest", "airport": "Budapest", "country": "HU", "country_name": "Hungary"},
    {"iata": "WAW", "city": "Warsaw", "airport": "Chopin", "country": "PL", "country_name": "Poland"},
    {"iata": "KRK", "city": "Krakow", "airport": "Krakow", "country": "PL", "country_name": "Poland"},
    {"iata": "FCO", "city": "Rome", "airport": "Fiumicino", "country": "IT", "country_name": "Italy"},
    {"iata": "MXP", "city": "Milan", "airport": "Malpensa", "country": "IT", "country_name": "Italy"},
    # US (Amadeus test coverage)
    {"iata": "JFK", "city": "New York", "airport": "John F Kennedy", "country": "US", "country_name": "United States"},
    {"iata": "EWR", "city": "Newark", "airport": "Newark Liberty", "country": "US", "country_name": "United States"},
    {"iata": "LAX", "city": "Los Angeles", "airport": "Los Angeles", "country": "US", "country_name": "United States"},
    {"iata": "SFO", "city": "San Francisco", "airport": "San Francisco", "country": "US", "country_name": "United States"},
    {"iata": "ORD", "city": "Chicago", "airport": "O'Hare", "country": "US", "country_name": "United States"},
    {"iata": "MIA", "city": "Miami", "airport": "Miami", "country": "US", "country_name": "United States"},
    {"iata": "ATL", "city": "Atlanta", "airport": "Hartsfield-Jackson", "country": "US", "country_name": "United States"},
    {"iata": "BOS", "city": "Boston", "airport": "Logan", "country": "US", "country_name": "United States"},
    {"iata": "SEA", "city": "Seattle", "airport": "Seattle-Tacoma", "country": "US", "country_name": "United States"},
    {"iata": "DEN", "city": "Denver", "airport": "Denver", "country": "US", "country_name": "United States"},
    {"iata": "DFW", "city": "Dallas", "airport": "Dallas Fort Worth", "country": "US", "country_name": "United States"},
    # India (Amadeus test coverage)
    {"iata": "DEL", "city": "New Delhi", "airport": "Indira Gandhi", "country": "IN", "country_name": "India"},
    {"iata": "BOM", "city": "Mumbai", "airport": "Chhatrapati Shivaji", "country": "IN", "country_name": "India"},
    {"iata": "BLR", "city": "Bangalore", "airport": "Kempegowda", "country": "IN", "country_name": "India"},
    {"iata": "CCU", "city": "Kolkata", "airport": "Netaji Subhas Chandra Bose", "country": "IN", "country_name": "India"},
    {"iata": "MAA", "city": "Chennai", "airport": "Chennai", "country": "IN", "country_name": "India"},
    # Middle East / Asia
    {"iata": "DXB", "city": "Dubai", "airport": "Dubai", "country": "AE", "country_name": "UAE"},
    {"iata": "AUH", "city": "Abu Dhabi", "airport": "Abu Dhabi", "country": "AE", "country_name": "UAE"},
    {"iata": "DOH", "city": "Doha", "airport": "Hamad", "country": "QA", "country_name": "Qatar"},
    {"iata": "SIN", "city": "Singapore", "airport": "Changi", "country": "SG", "country_name": "Singapore"},
    {"iata": "HKG", "city": "Hong Kong", "airport": "Hong Kong", "country": "HK", "country_name": "Hong Kong"},
    {"iata": "ICN", "city": "Seoul", "airport": "Incheon", "country": "KR", "country_name": "South Korea"},
    {"iata": "NRT", "city": "Tokyo", "airport": "Narita", "country": "JP", "country_name": "Japan"},
    {"iata": "HND", "city": "Tokyo", "airport": "Haneda", "country": "JP", "country_name": "Japan"},
    {"iata": "PEK", "city": "Beijing", "airport": "Capital", "country": "CN", "country_name": "China"},
    {"iata": "PVG", "city": "Shanghai", "airport": "Pudong", "country": "CN", "country_name": "China"},
]

# Deduplicate by IATA (keep first). ROME is invalid IATA, FCO is correct.
_pop_dedup = {}
for loc in POPULAR_LOCATIONS:
    iata = (loc["iata"] or "").upper().strip()
    if len(iata) == 3 and iata not in _pop_dedup:
        _pop_dedup[iata] = loc
POPULAR_LOCATIONS = list(_pop_dedup.values())


def normalize_input(query: str) -> str:
    """
    Trim, collapse whitespace, normalize unicode.
    """
    if not query or not isinstance(query, str):
        return ""
    s = " ".join(str(query).split()).strip()
    if not s:
        return ""
    try:
        s = unicodedata.normalize("NFKC", s)
    except Exception:
        pass
    return s


def looks_like_iata(s: str) -> bool:
    """
    True if string looks like a 3-letter IATA code.
    """
    if not s or not isinstance(s, str):
        return False
    s = s.strip().upper()
    if len(s) != 3:
        return False
    return bool(re.match(r"^[A-Z]{3}$", s))


def _to_location_result(
    iata: str,
    city: str,
    airport: str,
    country: str,
    country_name: str,
    source: str,
) -> LocationResult:
    label = f"{city} ({iata})" if city and iata else f"{airport or city} ({iata})"
    return LocationResult(
        label=label,
        city_name=city or "",
        airport_name=airport or "",
        iata_code=iata.upper() if iata else "",
        country_code=(country or "").upper(),
        country_name=country_name or "",
        source=source,
    )


def search_local(query: str, limit: int = 10) -> list[LocationResult]:
    """
    Search POPULAR_LOCATIONS by IATA, city, or airport name.
    Case-insensitive partial match.
    Returns list of LocationResult, sorted: exact IATA first, then city start, then airport.
    """
    q = normalize_input(query)
    if not q:
        return []

    q_lower = q.lower()
    q_upper = q.upper()

    exact_iata: list[LocationResult] = []
    city_matches: list[LocationResult] = []
    airport_matches: list[LocationResult] = []
    partial: list[LocationResult] = []

    for loc in POPULAR_LOCATIONS:
        iata = (loc.get("iata") or "").upper()
        city = (loc.get("city") or "").lower()
        airport = (loc.get("airport") or "").lower()
        country = (loc.get("country") or "").upper()
        country_name = (loc.get("country_name") or "").lower()

        res = _to_location_result(
            iata,
            loc.get("city", ""),
            loc.get("airport", ""),
            loc.get("country", ""),
            loc.get("country_name", ""),
            "local",
        )

        if q_upper == iata:
            exact_iata.append(res)
        elif city.startswith(q_lower) or q_lower in city:
            city_matches.append(res)
        elif airport.startswith(q_lower) or q_lower in airport:
            airport_matches.append(res)
        elif q_upper in iata or q_lower in city or q_lower in airport or q_lower in country_name:
            partial.append(res)

    # Deduplicate by iata_code, preserve order
    seen = set()
    out: list[LocationResult] = []
    for lst in (exact_iata, city_matches, airport_matches, partial):
        for r in lst:
            code = r.get("iata_code") or ""
            if code and code not in seen:
                seen.add(code)
                out.append(r)
                if len(out) >= limit:
                    return out
    return out[:limit]


def iata_to_city(iata: str) -> str:
    """Resolve IATA code to city name. Returns city or empty string."""
    if not iata or not isinstance(iata, str):
        return ""
    q = iata.strip().upper()
    if len(q) != 3:
        return ""
    for loc in POPULAR_LOCATIONS:
        if (loc.get("iata") or "").upper() == q:
            return loc.get("city", "") or ""
    return ""


def iata_to_country(iata: str) -> str:
    """Resolve IATA code to country code (e.g. PL, AZ)."""
    if not iata or not isinstance(iata, str):
        return ""
    q = iata.strip().upper()
    if len(q) != 3:
        return ""
    for loc in POPULAR_LOCATIONS:
        if (loc.get("iata") or "").upper() == q:
            return (loc.get("country") or "").upper() or ""
    return ""


def resolve_to_iata_local(query: str) -> str | None:
    """
    Resolve query to a single IATA code using only local data.
    Returns IATA or None.
    """
    q = normalize_input(query)
    if not q:
        return None

    # Exact 3-letter IATA in our list
    if looks_like_iata(q):
        for loc in POPULAR_LOCATIONS:
            if (loc.get("iata") or "").upper() == q.upper():
                return q.upper()

    results = search_local(q, limit=1)
    if results:
        return (results[0].get("iata_code") or "").upper() or None
    return None
