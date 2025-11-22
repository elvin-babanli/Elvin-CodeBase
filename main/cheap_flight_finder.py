# main/cheap_flight_finder.py
import os
import requests
from dotenv import load_dotenv
from django.shortcuts import render

load_dotenv()

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
OFFERS_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"


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


def get_offers(origin: str, destination: str, depart_date: str, currency: str, max_items: int = 10) -> dict:
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "originLocationCode": origin.upper().strip(),
        "destinationLocationCode": destination.upper().strip(),
        "departureDate": depart_date.strip(),
        "adults": 1,
        "currencyCode": currency.upper().strip(),
        "max": max_items,
    }
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


# ---- Django VIEW (views.py-sız) ----
def cheap_flight_finder_view(request):
    origin = (request.GET.get("origin") or "").upper().strip()
    destination = (request.GET.get("destination") or "").upper().strip()
    depart_date = (request.GET.get("depart_date") or "").strip()  # YYYY-MM-DD
    currency = (request.GET.get("currency") or "USD").upper().strip()

    error = None
    result = None  # {"price": 123.45, "currency": "USD", "segments": [...]}
    sample_rows = []

    if origin and destination and depart_date:
        try:
            offers = get_offers(origin, destination, depart_date, currency)
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
        },
    )
