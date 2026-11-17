"""OLO Bratislava waste pickups."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .api import OloClient
from .const import DOMAIN, USER_AGENT_FORMAT
from .coordinator import OloCoordinator, roll_to_day

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]

type OloConfigEntry = ConfigEntry[OloCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OloConfigEntry) -> bool:
    """Set up one OLO address."""
    version = (await async_get_integration(hass, DOMAIN)).version
    client = OloClient(async_get_clientsession(hass), USER_AGENT_FORMAT.format(version=version))
    coordinator = OloCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _on_midnight(_now: datetime) -> None:
        # Move sensors and the calendar event to the new day without a request.
        if coordinator.data is not None:
            coordinator.async_set_updated_data(roll_to_day(coordinator.data, dt_util.now().date()))

    entry.async_on_unload(async_track_time_change(hass, _on_midnight, hour=0, minute=0, second=5))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OloConfigEntry) -> bool:
    """Unload one OLO address."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
