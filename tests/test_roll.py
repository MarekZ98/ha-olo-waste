"""`roll_to_day`: the midnight roll recomputes collections from the stored rules."""

from __future__ import annotations

import json
import sys
import types
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# `coordinator` imports Home Assistant; register minimal stand-ins (as conftest.py does for
# the package) so the pure helper can be tested without Home Assistant installed.
if "homeassistant" not in sys.modules:

    class _DataUpdateCoordinator[T]:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    _stubs: dict[str, dict[str, Any]] = {
        "homeassistant": {},
        "homeassistant.config_entries": {"ConfigEntry": object},
        "homeassistant.core": {"HomeAssistant": object},
        "homeassistant.helpers": {},
        "homeassistant.helpers.update_coordinator": {
            "DataUpdateCoordinator": _DataUpdateCoordinator,
            "UpdateFailed": Exception,
        },
        "homeassistant.util": {},
        "homeassistant.util.dt": {},
    }
    for _name, _attrs in _stubs.items():
        _module = types.ModuleType(_name)
        _module.__dict__.update(_attrs)
        sys.modules[_name] = _module
    sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]  # type: ignore[attr-defined]

from custom_components.olo_waste.api import parse_pickup_rows
from custom_components.olo_waste.const import HORIZON_DAYS
from custom_components.olo_waste.coordinator import OloData, roll_to_day
from custom_components.olo_waste.decoder import collections, decode_rows

FIXTURES = Path(__file__).parent / "fixtures"
ROWS = parse_pickup_rows(json.loads((FIXTURES / "pickup-days-sample.json").read_text(encoding="utf-8")))
# Fetched on a Thursday with a mixed pickup, valid long enough for the horizon to be full.
FETCHED = date(2026, 11, 5)
RULES = decode_rows(ROWS, reference=FETCHED, valid_until=date(2027, 12, 31)).rules
DATA = OloData(
    address="Vzorová 1,3",
    collections=collections(RULES, FETCHED, FETCHED + timedelta(days=HORIZON_DAYS)),
    kinds=["mixed", "plastic", "paper", "glass", "bio", "kitchen_bio"],
    rules=RULES,
)


def test_drops_past_dates_and_keeps_the_horizon() -> None:
    today = FETCHED + timedelta(days=1)
    rolled = roll_to_day(DATA, today)

    assert any(c.date == FETCHED for c in DATA.collections)
    assert rolled.collections
    assert min(c.date for c in rolled.collections) >= today
    assert max(c.date for c in rolled.collections) <= today + timedelta(days=HORIZON_DAYS)
    assert rolled.collections == collections(RULES, today, today + timedelta(days=HORIZON_DAYS))
    # The new last day of the horizon is covered, the old data did not reach it.
    assert max(c.date for c in rolled.collections) > max(c.date for c in DATA.collections)


def test_keeps_everything_else() -> None:
    rolled = roll_to_day(DATA, FETCHED + timedelta(days=7))

    assert (rolled.address, rolled.kinds, rolled.rules) == (DATA.address, DATA.kinds, DATA.rules)
    assert DATA.collections[0].date == FETCHED  # the input is not modified
