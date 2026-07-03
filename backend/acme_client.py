"""ACME Markets API client using the shared Albertsons/Safeway platform."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OKTA_TOKEN_URL = "https://albertsons.okta.com/oauth2/ausp6soxrIyPrm8rS2p6/v1/token"
OKTA_CLIENT_ID = "0oap6kkp7Sefg24rB2p6"
OKTA_CLIENT_SECRET = "4UpmzD4hlF2VYQqYjDUoamgLu2Bo1OzagpfG7yus"

NIMBUS_BASE = "https://nimbus.safeway.com"
MANUFACTURER_COUPONS_URL = f"{NIMBUS_BASE}/emmd/service/gallery/offer/mfg"
PERSONALIZED_COUPONS_URL = f"{NIMBUS_BASE}/emmd/service/gallery/offer/pd"
CLIP_COUPONS_URL = f"{NIMBUS_BASE}/Clipping1/services/clip/items"
MYLIST_URL = f"{NIMBUS_BASE}/emmd/service/mylist/default/details"
CLIPPED_OFFERS_URL = f"{NIMBUS_BASE}/emmd/service/mylist/clipped/details"

MOBILE_USER_AGENT = "Safeway/3373 CFNetwork/978.0.7 Darwin/18.6.0"


@dataclass
class Coupon:
    coupon_id: str
    item_type: str
    description: str
    name: str
    brand: str
    category: str
    is_clipped: bool = False
    source: str = "manufacturer"


@dataclass
class GroceryListItem:
    name: str
    item_id: str | None = None
    item_type: str | None = None
    source: str = "local"


class AcmeClientError(Exception):
    pass


class AcmeAuthError(AcmeClientError):
    pass


class AcmeClient:
    """Client for ACME Markets digital coupons and shopping list."""

    def __init__(self, access_token: str, store_id: str):
        self.access_token = access_token
        self.store_id = store_id
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": MOBILE_USER_AGENT,
        }

    def _get(self, url: str) -> dict[str, Any]:
        response = self._client.get(
            url,
            params={"storeId": self.store_id},
            headers=self._headers(),
            cookies={"swyConsumerDirectoryPro": self.access_token},
        )
        if response.status_code == 401:
            raise AcmeAuthError("Session expired. Please sign in again.")
        if response.status_code != 200:
            raise AcmeClientError(f"Request failed ({response.status_code}): {response.text[:200]}")
        return response.json()

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            url,
            params={"storeId": self.store_id},
            headers=self._headers(),
            json=payload,
        )
        if response.status_code == 401:
            raise AcmeAuthError("Session expired. Please sign in again.")
        if response.status_code != 200:
            raise AcmeClientError(f"Clip failed ({response.status_code}): {response.text[:200]}")
        try:
            return response.json()
        except Exception:
            return {"status": "ok"}

    @staticmethod
    def authenticate(email: str, password: str) -> str:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                OKTA_TOKEN_URL,
                data={
                    "username": email,
                    "password": password,
                    "grant_type": "password",
                    "scope": "openid profile offline_access",
                },
                auth=(OKTA_CLIENT_ID, OKTA_CLIENT_SECRET),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": MOBILE_USER_AGENT,
                },
            )

        if response.status_code != 200:
            error = response.json() if response.content else {}
            message = error.get("error_description") or error.get("error") or "Invalid credentials"
            raise AcmeAuthError(message)

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise AcmeAuthError("No access token returned")
        return token

    def get_clipped_coupon_ids(self) -> set[str]:
        clipped: set[str] = set()
        for url in (CLIPPED_OFFERS_URL, MYLIST_URL):
            try:
                data = self._get(url)
            except AcmeClientError:
                continue

            for key in ("clippedOffers", "shoppingList", "items", "offers"):
                items = data.get(key, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    coupon_id = (
                        item.get("couponID")
                        or item.get("offerID")
                        or item.get("offerId")
                        or item.get("itemId")
                    )
                    if coupon_id:
                        clipped.add(str(coupon_id))
        return clipped

    def get_all_coupons(self) -> list[Coupon]:
        clipped_ids = self.get_clipped_coupon_ids()
        coupons: list[Coupon] = []

        mfg_data = self._get(MANUFACTURER_COUPONS_URL)
        for raw in mfg_data.get("manufacturerCoupons", []):
            coupon_id = str(raw.get("couponID", ""))
            if not coupon_id:
                continue
            coupons.append(
                Coupon(
                    coupon_id=coupon_id,
                    item_type=str(raw.get("offerPgm", "MF")),
                    description=str(raw.get("description", "")),
                    name=str(raw.get("name", raw.get("brandName", ""))),
                    brand=str(raw.get("brandName", "")),
                    category=str(raw.get("categoryName", "")),
                    is_clipped=coupon_id in clipped_ids,
                    source="manufacturer",
                )
            )

        pd_data = self._get(PERSONALIZED_COUPONS_URL)
        for raw in pd_data.get("personalizedDeals", []):
            coupon_id = str(raw.get("offerID", ""))
            if not coupon_id:
                continue
            coupons.append(
                Coupon(
                    coupon_id=coupon_id,
                    item_type=str(raw.get("offerPgm", "PD")),
                    description=str(raw.get("description", "")),
                    name=str(raw.get("name", "")),
                    brand=str(raw.get("brandName", "")),
                    category=str(raw.get("categoryName", "")),
                    is_clipped=coupon_id in clipped_ids,
                    source="personalized",
                )
            )

        return coupons

    def clip_coupon(self, coupon_id: str, item_type: str) -> None:
        payload = {
            "items": [
                {"clipType": "L", "itemId": coupon_id, "itemType": item_type},
                {"clipType": "C", "itemId": coupon_id, "itemType": item_type},
            ]
        }
        self._post(CLIP_COUPONS_URL, payload)

    def get_acme_grocery_list(self) -> list[GroceryListItem]:
        """Fetch grocery list items from the ACME app when available."""
        items: list[GroceryListItem] = []
        try:
            data = self._get(MYLIST_URL)
        except AcmeClientError:
            return items

        for key in ("shoppingList", "items", "products", "listItems"):
            raw_items = data.get(key, [])
            if not isinstance(raw_items, list):
                continue
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                name = (
                    raw.get("name")
                    or raw.get("productName")
                    or raw.get("description")
                    or raw.get("itemName")
                    or raw.get("title")
                )
                if not name:
                    continue
                items.append(
                    GroceryListItem(
                        name=str(name),
                        item_id=str(raw.get("itemId") or raw.get("offerId") or raw.get("productId") or ""),
                        item_type=str(raw.get("itemType") or raw.get("offerPgm") or ""),
                        source="acme",
                    )
                )
        return items
