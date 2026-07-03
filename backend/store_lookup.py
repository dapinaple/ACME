"""Look up ACME Markets stores by ZIP code or city."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

STORE_INDEX_PATH = Path(__file__).resolve().parent / "data" / "stores.json"
LOCAL_BASE = "https://local.acmemarkets.com"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
STORE_ID_PATTERN = re.compile(r"storeId=(\d+)", re.IGNORECASE)
STORE_PAGE_PATTERN = re.compile(
    r"https://local\.acmemarkets\.com/[a-z]{2}/[^/<]+/[^/<]+\.html"
)


@dataclass
class Store:
    store_id: str
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    url: str


class StoreLookupError(Exception):
    pass


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@lru_cache(maxsize=256)
def _geocode_zip(zip_code: str) -> tuple[float, float]:
    with httpx.Client(timeout=20.0, headers={"User-Agent": "ACME-Coupon-Clipper/1.0"}) as client:
        response = client.get(
            NOMINATIM_URL,
            params={
                "postalcode": zip_code,
                "country": "US",
                "format": "json",
                "limit": 1,
            },
        )
        response.raise_for_status()
        results = response.json()

    if not results:
        raise StoreLookupError(f"No location found for ZIP code {zip_code}")

    return float(results[0]["lat"]), float(results[0]["lon"])


def _load_store_index() -> list[Store]:
    if not STORE_INDEX_PATH.exists():
        raise StoreLookupError(
            "Store index is missing. Run backend/scripts/build_store_index.py first."
        )

    raw = json.loads(STORE_INDEX_PATH.read_text(encoding="utf-8"))
    stores: list[Store] = []
    for item in raw:
        stores.append(
            Store(
                store_id=str(item["store_id"]),
                name=str(item.get("name", "ACME Markets")),
                address=str(item.get("address", "")),
                city=str(item.get("city", "")),
                state=str(item.get("state", "")),
                zip_code=str(item.get("zip_code", "")),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                url=str(item.get("url", "")),
            )
        )
    return stores


def search_stores(
    zip_code: str | None = None,
    query: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    stores = _load_store_index()
    matches: list[tuple[float, Store]] = []

    if zip_code:
        clean_zip = re.sub(r"\D", "", zip_code)[:5]
        if len(clean_zip) != 5:
            raise StoreLookupError("Enter a valid 5-digit ZIP code")

        exact = [store for store in stores if store.zip_code.startswith(clean_zip)]
        if exact:
            for store in exact[:limit]:
                matches.append((0.0, store))
        else:
            lat, lon = _geocode_zip(clean_zip)
            for store in stores:
                distance = _haversine_miles(lat, lon, store.latitude, store.longitude)
                matches.append((distance, store))

    elif query:
        needle = query.strip().lower()
        if not needle:
            raise StoreLookupError("Enter a city name or address to search")

        for store in stores:
            haystack = " ".join(
                [store.name, store.address, store.city, store.state, store.zip_code]
            ).lower()
            if needle in haystack:
                matches.append((0.0, store))
    else:
        raise StoreLookupError("Provide a ZIP code or search term")

    matches.sort(key=lambda item: item[0])
    results: list[dict[str, Any]] = []
    for distance, store in matches[:limit]:
        results.append(
            {
                "store_id": store.store_id,
                "name": store.name,
                "address": store.address,
                "city": store.city,
                "state": store.state,
                "zip_code": store.zip_code,
                "distance_miles": round(distance, 1) if distance else 0.0,
                "url": store.url,
            }
        )
    return results


def parse_store_id_from_html(html: str) -> str | None:
    match = STORE_ID_PATTERN.search(html)
    return match.group(1) if match else None
