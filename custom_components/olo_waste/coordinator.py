"""Daily refresh of the OLO pickup rules of one address."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date, timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OloApiError, OloClient
from .const import CONF_ADDRESS, DOMAIN, HORIZON_DAYS, UPDATE_INTERVAL, WASTE_TYPES
from .decoder import Collection, WasteRule, collections, decode_rows

_LOGGER = logging.getLogger(__name__)

_KIND_ORDER = list(WASTE_TYPES.values())


@dataclass(frozen=True)
class OloData:
    """What the entities read."""

    address: str
    collections: list[Collection]
    # Kinds that have at least one rule, in the order of WASTE_TYPES.
    kinds: list[str]
    rules: list[WasteRule]


def roll_to_day(data: OloData, today: date) -> OloData:
    """`data` with collections recomputed for [today, today + HORIZON_DAYS]; no request."""
    return replace(data, collections=collections(data.rules, today, today + timedelta(days=HORIZON_DAYS)))


class OloCoordinator(DataUpdateCoordinator[OloData]):
    """Fetches the pickup rows once a day and decodes them."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, client: OloClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.address: str = config_entry.data[CONF_ADDRESS]
        self._logged: set[str] = set()

    async def _async_update_data(self) -> OloData:
        try:
            rows = await self.client.pickup_rows(self.address)
        except (OloApiError, aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"OLO request failed: {err}") from err

        reference = dt_util.now().date()
        # OLO publishes the schedule per calendar year; never guess the next one.
        valid_until = date(reference.year, 12, 31)
        result = decode_rows(rows, reference=reference, valid_until=valid_until)

        for text in [f"unknown waste type {t!r}" for t in result.unknown_types] + [
            f"unreadable row {r!r}" for r in result.invalid
        ]:
            if text not in self._logged:
                self._logged.add(text)
                _LOGGER.warning("OLO %s: skipped %s", self.address, text)

        rule_kinds = {rule.kind for rule in result.rules}
        return OloData(
            address=self.address,
            collections=collections(result.rules, reference, reference + timedelta(days=HORIZON_DAYS)),
            kinds=[kind for kind in _KIND_ORDER if kind in rule_kinds],
            rules=result.rules,
        )
