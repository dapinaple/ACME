"""Tests for store lookup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from store_lookup import search_stores


def test_search_by_zip_returns_nearby_stores():
    stores = search_stores(zip_code="19103", limit=3)
    assert len(stores) > 0
    assert all(store["store_id"] for store in stores)
