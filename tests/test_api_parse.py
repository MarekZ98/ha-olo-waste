"""Parse helpers of the OLO client (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.olo_waste.api import OloApiError, PickupRow, parse_pickup_rows, parse_search

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_search_fixture() -> None:
    hits = parse_search(load("search-sample.json"))
    assert len(hits) == 10
    assert hits[0] == "Vzorová 1,3"
    assert hits[:4] == ["Vzorová 1,3", "Vzorová 1,3,5,7", "Vzorová 2A,2B", "Vzorová 5,7"]


def test_parse_search_is_distinct_and_keeps_order() -> None:
    raw = {"hits": [{"pickup-day": {"address": a}} for a in ("B 1", "A 2", "B 1", "C 3", "A 2")]}
    assert parse_search(raw) == ["B 1", "A 2", "C 3"]


def test_parse_pickup_rows_fixture() -> None:
    rows = parse_pickup_rows(load("pickup-days-sample.json"))
    assert len(rows) == 12
    assert rows[0] == PickupRow(waste_type="Sklo", frequency="[4,4]", frequency_season=None)
    assert PickupRow("BRO", "[-,1];[-,1,-,-]", "28/02-30/11, 01/12-27/02") in rows


def test_parse_pickup_rows_skips_rows_without_type_or_frequency() -> None:
    raw = {
        "data": {
            "pickupDays": {
                "data": [
                    {"attributes": {"wasteType": None, "frequency": "[1,1]", "frequencySeason": None}},
                    {"attributes": {"wasteType": "Plast", "frequency": None, "frequencySeason": None}},
                    {"attributes": {"wasteType": "Plast", "frequency": "[2,2]", "frequencySeason": None}},
                ]
            }
        }
    }
    assert parse_pickup_rows(raw) == [PickupRow("Plast", "[2,2]", None)]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"errors": [{"message": "boom"}]}, "boom"),
        ({"data": None}, "no data"),
        ({}, "no data"),
        ({"data": {"pickupDays": {"data": "nope"}}}, "unexpected"),
        ({"data": {"pickupDays": {"data": [{"attributes": {"wasteType": 1, "frequency": "[1]"}}]}}}, "unexpected"),
        ([], "unexpected"),
    ],
)
def test_parse_pickup_rows_errors(raw: object, message: str) -> None:
    with pytest.raises(OloApiError, match=message):
        parse_pickup_rows(raw)


@pytest.mark.parametrize("raw", [{"nope": 1}, {"hits": [{"x": 1}]}, {"hits": [{"pickup-day": {"address": ""}}]}, None])
def test_parse_search_errors(raw: object) -> None:
    with pytest.raises(OloApiError, match="unexpected"):
        parse_search(raw)
