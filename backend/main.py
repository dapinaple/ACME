"""ACME Coupon Clipper - mobile-friendly web API."""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from acme_client import AcmeAuthError, AcmeClient, AcmeClientError
from matcher import CouponMatch, match_coupons_to_list
from store_lookup import StoreLookupError, search_stores

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(os.path.dirname(APP_DIR), "frontend")

SESSION_TTL_SECONDS = 60 * 60 * 8

sessions: dict[str, dict[str, Any]] = {}
local_lists: dict[str, list[str]] = {}


class LoginRequest(BaseModel):
    email: str = Field(description="ACME for U phone number or email address")
    password: str
    store_id: str = Field(min_length=1, description="Your ACME store ID")


class ListUpdateRequest(BaseModel):
    items: list[str]


class ClipRequest(BaseModel):
    coupon_ids: list[str] | None = None
    clip_all: bool = False


app = FastAPI(title="ACME Coupon Clipper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cleanup_sessions() -> None:
    now = time.time()
    expired = [token for token, data in sessions.items() if data["expires_at"] < now]
    for token in expired:
        client = sessions[token].get("client")
        if client:
            client.close()
        sessions.pop(token, None)


def _get_session(request: Request) -> dict[str, Any]:
    _cleanup_sessions()
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Not signed in")
    return sessions[token]


def _coupon_to_dict(coupon) -> dict[str, Any]:
    return {
        "coupon_id": coupon.coupon_id,
        "item_type": coupon.item_type,
        "description": coupon.description,
        "name": coupon.name,
        "brand": coupon.brand,
        "category": coupon.category,
        "is_clipped": coupon.is_clipped,
        "source": coupon.source,
    }


def _match_to_dict(match: CouponMatch) -> dict[str, Any]:
    return {
        **_coupon_to_dict(match.coupon),
        "matched_terms": match.matched_terms,
        "score": match.score,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stores/search")
def store_search(zip: str | None = None, q: str | None = None) -> dict[str, Any]:
    try:
        stores = search_stores(zip_code=zip, query=q)
    except StoreLookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"stores": stores, "count": len(stores)}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    try:
        access_token = AcmeClient.authenticate(payload.email, payload.password)
        client = AcmeClient(access_token, payload.store_id)
        client.get_all_coupons()
    except AcmeAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AcmeClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_token = secrets.token_urlsafe(32)
    sessions[session_token] = {
        "email": payload.email,
        "store_id": payload.store_id,
        "client": client,
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }

    if payload.email not in local_lists:
        local_lists[payload.email] = []

    return {
        "token": session_token,
        "email": payload.email,
        "store_id": payload.store_id,
    }


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, str]:
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token in sessions:
        client = sessions[token].get("client")
        if client:
            client.close()
        sessions.pop(token, None)
    return {"status": "signed_out"}


@app.get("/api/list")
def get_list(request: Request) -> dict[str, Any]:
    session = _get_session(request)
    email = session["email"]
    local_items = local_lists.get(email, [])

    acme_items: list[str] = []
    try:
        acme_items = [item.name for item in session["client"].get_acme_grocery_list()]
    except (AcmeClientError, AcmeAuthError):
        pass

    merged = list(dict.fromkeys([*local_items, *acme_items]))
    return {
        "items": merged,
        "local_items": local_items,
        "acme_items": acme_items,
    }


@app.put("/api/list")
def update_list(payload: ListUpdateRequest, request: Request) -> dict[str, Any]:
    session = _get_session(request)
    cleaned = [item.strip() for item in payload.items if item.strip()]
    local_lists[session["email"]] = cleaned
    return {"items": cleaned}


@app.post("/api/list/sync")
def sync_list(request: Request) -> dict[str, Any]:
    session = _get_session(request)
    client: AcmeClient = session["client"]
    try:
        acme_items = [item.name for item in client.get_acme_grocery_list()]
    except AcmeAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AcmeClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    email = session["email"]
    existing = local_lists.get(email, [])
    merged = list(dict.fromkeys([*existing, *acme_items]))
    local_lists[email] = merged
    return {"items": merged, "imported_from_acme": acme_items}


@app.get("/api/coupons")
def list_coupons(request: Request) -> dict[str, Any]:
    session = _get_session(request)
    try:
        coupons = session["client"].get_all_coupons()
    except AcmeAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AcmeClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "coupons": [_coupon_to_dict(coupon) for coupon in coupons],
        "total": len(coupons),
        "clipped": sum(1 for coupon in coupons if coupon.is_clipped),
    }


@app.get("/api/coupons/matches")
def coupon_matches(request: Request) -> dict[str, Any]:
    session = _get_session(request)
    email = session["email"]
    grocery_items = local_lists.get(email, [])

    try:
        acme_items = [item.name for item in session["client"].get_acme_grocery_list()]
        grocery_items = list(dict.fromkeys([*grocery_items, *acme_items]))
        coupons = session["client"].get_all_coupons()
    except AcmeAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AcmeClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    matches = match_coupons_to_list(grocery_items, coupons)
    return {
        "grocery_items": grocery_items,
        "matches": [_match_to_dict(match) for match in matches],
        "match_count": len(matches),
    }


@app.post("/api/coupons/clip")
def clip_coupons(payload: ClipRequest, request: Request) -> dict[str, Any]:
    session = _get_session(request)
    client: AcmeClient = session["client"]
    email = session["email"]

    try:
        coupons = client.get_all_coupons()
    except AcmeAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AcmeClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    coupon_map = {coupon.coupon_id: coupon for coupon in coupons}
    to_clip: list = []

    if payload.clip_all:
        to_clip = [coupon for coupon in coupons if not coupon.is_clipped]
    elif payload.coupon_ids:
        to_clip = [coupon_map[cid] for cid in payload.coupon_ids if cid in coupon_map and not coupon_map[cid].is_clipped]
    else:
        grocery_items = local_lists.get(email, [])
        acme_items = [item.name for item in client.get_acme_grocery_list()]
        grocery_items = list(dict.fromkeys([*grocery_items, *acme_items]))
        matches = match_coupons_to_list(grocery_items, coupons)
        to_clip = [match.coupon for match in matches]

    clipped: list[str] = []
    errors: list[str] = []

    for coupon in to_clip:
        try:
            client.clip_coupon(coupon.coupon_id, coupon.item_type)
            clipped.append(coupon.coupon_id)
        except AcmeClientError as exc:
            errors.append(f"{coupon.name or coupon.description}: {exc}")

    return {
        "requested": len(to_clip),
        "clipped": len(clipped),
        "clipped_ids": clipped,
        "errors": errors,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
