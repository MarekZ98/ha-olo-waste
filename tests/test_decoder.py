"""Decoder of the OLO frequency rules."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from custom_components.olo_waste.api import PickupRow, parse_pickup_rows
from custom_components.olo_waste.decoder import (
    IsoWeekCycle,
    Season,
    WasteRule,
    collections,
    decode_rows,
    in_season,
    iso_week_of,
)

FIXTURES = Path(__file__).parent / "fixtures"

# The rows of the recorded answer for "Vzorová 1,3" (12 rows, 6 distinct).
ROWS = parse_pickup_rows(json.loads((FIXTURES / "pickup-days-sample.json").read_text(encoding="utf-8")))

DECODED = decode_rows(ROWS, reference=date(2026, 11, 5), valid_until=date(2026, 12, 31))


def dates_of(rules: list[WasteRule], start: date, end: date) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in collections(rules, start, end):
        out.setdefault(c.kind, []).append(c.date.strftime("%m-%d"))
    return out


def test_dedupes_rows_and_maps_every_waste_type() -> None:
    assert len(ROWS) == 12
    assert DECODED.unknown_types == []
    assert DECODED.invalid == []
    assert {r.kind for r in DECODED.rules} == {"mixed", "plastic", "paper", "glass", "bio", "kitchen_bio"}
    # mixed Mon + Thu, plastic, paper, glass, kitchen bio Wed + Sat (summer) + Wed (winter), bio 2 seasons.
    assert len(DECODED.rules) == 10
    for rule in DECODED.rules:
        assert rule.valid_until == date(2026, 12, 31)
        assert rule.anchor_date.isoweekday() == rule.weekday


def test_reduces_equal_cycle_elements_to_weekly_and_keeps_real_cycles() -> None:
    mixed = [r for r in DECODED.rules if r.kind == "mixed"]
    assert [(r.weekday, r.interval_weeks, r.iso_week_cycle) for r in mixed] == [(1, 1, None), (4, 1, None)]
    bio = [r for r in DECODED.rules if r.kind == "bio"]
    assert [(r.season, r.iso_week_cycle, r.weekday) for r in bio] == [
        (Season("02-28", "11-30"), IsoWeekCycle(2, 1), 1),
        (Season("12-01", "02-27"), IsoWeekCycle(4, 1), 1),
    ]


def test_matches_olo_sk_for_the_next_8_weeks() -> None:
    assert dates_of(DECODED.rules, date(2026, 11, 5), date(2026, 12, 31)) == {
        "mixed": [
            "11-05", "11-09", "11-12", "11-16", "11-19", "11-23", "11-26", "11-30", "12-03",
            "12-07", "12-10", "12-14", "12-17", "12-21", "12-24", "12-28", "12-31",
        ],
        "plastic": ["11-10", "11-17", "11-24", "12-01", "12-08", "12-15", "12-22", "12-29"],
        "paper": ["11-07", "11-14", "11-21", "11-28", "12-05", "12-12", "12-19", "12-26"],
        "glass": ["11-05", "11-12", "11-19", "11-26", "12-03", "12-10", "12-17", "12-24", "12-31"],
        # Winter season: Wednesdays only.
        "kitchen_bio": ["11-11", "11-18", "11-25", "12-02", "12-09", "12-16", "12-23", "12-30"],
        # Every 2 weeks until 30. 11. (even ISO weeks), then every 4 weeks (7. 12. = ISO week 50; week 53 is not one).
        "bio": ["11-09", "11-23", "12-07"],
    }


def test_does_not_extrapolate_past_the_published_year() -> None:
    assert dates_of(DECODED.rules, date(2027, 1, 1), date(2027, 1, 31)) == {}


def test_summer_season_of_kitchen_bio_and_bio_season_change() -> None:
    rules = decode_rows(ROWS, reference=date(2026, 11, 5)).rules
    assert dates_of(rules, date(2026, 6, 1), date(2026, 6, 14))["kitchen_bio"] == ["06-03", "06-06", "06-10", "06-13"]
    assert dates_of(rules, date(2026, 6, 1), date(2026, 6, 30))["bio"] == ["06-08", "06-22"]
    # Winter (weeks 2, 6) -> 28. 2. the summer cycle starts (week 10, 12).
    assert dates_of(rules, date(2026, 1, 1), date(2026, 3, 20))["bio"] == ["01-05", "02-02", "03-02", "03-16"]
    # Kitchen bio waste across the season border 31. 3. / 1. 4. (wraps the new year).
    assert dates_of(rules, date(2026, 3, 25), date(2026, 4, 8))["kitchen_bio"] == ["03-25", "04-01", "04-04", "04-08"]


def test_skips_unknown_waste_types_and_malformed_rows() -> None:
    result = decode_rows(
        [
            PickupRow("Kovy", "[1,1]", None),
            PickupRow("Kovy", "[1,1]", None),
            PickupRow("Plast", "[2,x]", None),
            PickupRow("Sklo", "[4];[5]", None),
            PickupRow("Papier", "[6,-]", None),
        ],
        reference=date(2026, 11, 5),
    )
    assert result.unknown_types == ["Kovy"]
    assert result.invalid == ["Plast: [2,x]", "Sklo: [4];[5]"]
    assert result.rules == [
        WasteRule(kind="paper", weekday=6, interval_weeks=2, anchor_date=date(2026, 10, 24), iso_week_cycle=IsoWeekCycle(2, 0))
    ]


def test_fixture_from_2026_11_15_next_28_days() -> None:
    reference = date(2026, 11, 15)
    result = decode_rows(ROWS, reference=reference, valid_until=date(2026, 12, 31))
    assert {r.kind for r in result.rules} == {"mixed", "plastic", "paper", "glass", "bio", "kitchen_bio"}
    found = collections(result.rules, reference, reference + timedelta(days=28))
    assert found
    assert found == sorted(found, key=lambda c: (c.date, c.kind))
    weekdays: dict[str, set[int]] = {}
    for rule in result.rules:
        weekdays.setdefault(rule.kind, set()).add(rule.weekday)
    for c in found:
        assert reference <= c.date <= reference + timedelta(days=28)
        assert c.date.isoweekday() in weekdays[c.kind]


def test_iso_week_across_new_year() -> None:
    d = date(2026, 12, 28)
    while d <= date(2027, 1, 4):
        assert iso_week_of(d) == d.isocalendar().week
        d += timedelta(days=1)
    # 2026 has 53 ISO weeks; 4. 1. 2027 starts week 1.
    assert iso_week_of(date(2026, 12, 31)) == 53
    assert iso_week_of(date(2027, 1, 4)) == 1


def test_season_wraps_the_new_year() -> None:
    winter = Season("12-01", "02-27")
    assert in_season(date(2026, 12, 1), winter)
    assert in_season(date(2027, 1, 15), winter)
    assert in_season(date(2027, 2, 27), winter)
    assert not in_season(date(2027, 2, 28), winter)
    assert not in_season(date(2026, 11, 30), winter)
    summer = Season("02-28", "11-30")
    assert in_season(date(2026, 2, 28), summer)
    assert not in_season(date(2026, 12, 1), summer)
