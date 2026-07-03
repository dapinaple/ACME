"""Build ACME store index from local.acmemarkets.com sitemap."""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from store_lookup import STORE_ID_PATTERN

SITEMAP_URL = "https://local.acmemarkets.com/sitemap.xml"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "stores.json"
STORE_URL_PATTERN = re.compile(
    r"^https://local\.acmemarkets\.com/[a-z]{2}/[^/]+/[^/]+\.html$"
)

LAT_PATTERN = re.compile(r'"lat(?:itude)?"\s*:\s*"?([-\d.]+)"?')
LON_PATTERN = re.compile(r'"lng(?:itude)?"\s*:\s*"?([-\d.]+)"?')
NAME_PATTERN = re.compile(r'"name"\s*:\s*"([^"]+)"')
LINE1_PATTERN = re.compile(r'"line1"\s*:\s*"([^"]+)"')
CITY_PATTERN = re.compile(r'"city"\s*:\s*"([^"]+)"')
REGION_PATTERN = re.compile(r'"region"\s*:\s*"([^"]+)"')
POSTAL_PATTERN = re.compile(r'"postalCode"\s*:\s*"([^"]+)"')
GEO_POSITION_PATTERN = re.compile(
    r'geo\.position"\s+content="([-\d.]+);([-\d.]+)"'
)


def _store_urls_from_sitemap(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: list[str] = []
    for node in root.findall("sm:url", namespace):
        loc = node.findtext("sm:loc", default="", namespaces=namespace)
        if STORE_URL_PATTERN.match(loc):
            urls.append(loc)
    return sorted(set(urls))


def _parse_store_page(url: str, html: str) -> dict | None:
    store_id_match = STORE_ID_PATTERN.search(html)
    if not store_id_match:
        return None

    latitude: float | None = None
    longitude: float | None = None

    lat_match = LAT_PATTERN.search(html)
    lon_match = LON_PATTERN.search(html)
    if lat_match and lon_match:
        latitude = float(lat_match.group(1))
        longitude = float(lon_match.group(1))
    else:
        geo_match = GEO_POSITION_PATTERN.search(html)
        if geo_match:
            latitude = float(geo_match.group(1))
            longitude = float(geo_match.group(2))

    if latitude is None or longitude is None:
        return None

    name = NAME_PATTERN.search(html)
    line1 = LINE1_PATTERN.search(html)
    city = CITY_PATTERN.search(html)
    region = REGION_PATTERN.search(html)
    postal = POSTAL_PATTERN.search(html)

    return {
        "store_id": store_id_match.group(1),
        "name": name.group(1) if name else "ACME Markets",
        "address": line1.group(1) if line1 else "",
        "city": city.group(1) if city else "",
        "state": region.group(1) if region else "",
        "zip_code": postal.group(1) if postal else "",
        "latitude": latitude,
        "longitude": longitude,
        "url": url,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=30.0, headers={"User-Agent": "ACME-Coupon-Clipper/1.0"}) as client:
        sitemap = client.get(SITEMAP_URL).text
        urls = _store_urls_from_sitemap(sitemap)
        print(f"Found {len(urls)} store pages in sitemap")

        stores_by_id: dict[str, dict] = {}
        for index, url in enumerate(urls, start=1):
            response = client.get(url)
            response.raise_for_status()
            parsed = _parse_store_page(url, response.text)
            if parsed:
                stores_by_id[parsed["store_id"]] = parsed
            if index % 20 == 0:
                print(f"Processed {index}/{len(urls)}")
            time.sleep(0.15)

    stores = sorted(stores_by_id.values(), key=lambda item: (item["state"], item["city"], item["address"]))
    OUTPUT_PATH.write_text(json.dumps(stores, indent=2), encoding="utf-8")
    print(f"Wrote {len(stores)} stores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
