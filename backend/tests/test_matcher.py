"""Tests for grocery list to coupon matching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from acme_client import Coupon
from matcher import match_coupons_to_list


def test_matches_milk_coupon():
    coupons = [
        Coupon(
            coupon_id="1",
            item_type="MF",
            description="Save $1.00 on any gallon of milk",
            name="Organic Valley Milk",
            brand="Organic Valley",
            category="Dairy",
        )
    ]
    matches = match_coupons_to_list(["milk", "bread"], coupons)
    assert len(matches) == 1
    assert "milk" in matches[0].matched_terms


def test_skips_already_clipped():
    coupons = [
        Coupon(
            coupon_id="1",
            item_type="MF",
            description="Save on cereal",
            name="Cheerios",
            brand="General Mills",
            category="Breakfast",
            is_clipped=True,
        )
    ]
    matches = match_coupons_to_list(["cereal"], coupons)
    assert matches == []
