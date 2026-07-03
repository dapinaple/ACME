"""Match grocery list items to available digital coupons."""

from __future__ import annotations

import re
from dataclasses import dataclass

from acme_client import Coupon

STOP_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "oz",
    "lb",
    "ct",
    "pkg",
    "size",
    "select",
    "varieties",
    "when",
    "you",
    "buy",
    "save",
    "off",
    "free",
}


@dataclass
class CouponMatch:
    coupon: Coupon
    matched_terms: list[str]
    score: float


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _keywords(text: str) -> set[str]:
    words = _normalize(text).split()
    return {word for word in words if len(word) > 2 and word not in STOP_WORDS}


def match_coupons_to_list(
    grocery_items: list[str],
    coupons: list[Coupon],
    min_score: float = 0.35,
) -> list[CouponMatch]:
    """Return coupons that likely apply to items on the grocery list."""
    if not grocery_items:
        return []

    list_keywords: set[str] = set()
    for item in grocery_items:
        list_keywords.update(_keywords(item))

    if not list_keywords:
        return []

    matches: list[CouponMatch] = []

    for coupon in coupons:
        if coupon.is_clipped:
            continue

        coupon_text = " ".join(
            part for part in (coupon.name, coupon.brand, coupon.description, coupon.category) if part
        )
        coupon_keywords = _keywords(coupon_text)
        if not coupon_keywords:
            continue

        overlap = list_keywords & coupon_keywords
        if not overlap:
            continue

        score = len(overlap) / max(len(list_keywords), 1)
        if score >= min_score:
            matches.append(
                CouponMatch(
                    coupon=coupon,
                    matched_terms=sorted(overlap),
                    score=round(score, 2),
                )
            )

    matches.sort(key=lambda match: match.score, reverse=True)
    return matches
