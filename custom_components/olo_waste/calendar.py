"""Calendar of OLO pickups."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import OloConfigEntry
from .const import DOMAIN, KIND_NAMES_SK
from .coordinator import OloCoordinator
from .decoder import Collection, collections


def device_info(entry: OloConfigEntry, address: str) -> DeviceInfo:
    """One service device per address."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"OLO {address}",
        manufacturer="OLO Bratislava",
        entry_type=DeviceEntryType.SERVICE,
    )


def _event(collection: Collection) -> CalendarEvent:
    return CalendarEvent(
        start=collection.date,
        end=collection.date + timedelta(days=1),
        summary=KIND_NAMES_SK.get(collection.kind, collection.kind),
        uid=f"{collection.kind}:{collection.date.isoformat()}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the calendar."""
    async_add_entities([OloCalendar(entry.runtime_data, entry)])


class OloCalendar(CoordinatorEntity[OloCoordinator], CalendarEntity):
    """All pickups of one address as all-day events."""

    _attr_has_entity_name = True
    _attr_translation_key = "pickups"

    def __init__(self, coordinator: OloCoordinator, entry: OloConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = device_info(entry, coordinator.address)

    @property
    def event(self) -> CalendarEvent | None:
        """The next pickup from today (today's pickup counts)."""
        today = dt_util.now().date()
        for collection in self.coordinator.data.collections:
            if collection.date >= today:
                return _event(collection)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Pickups in a range; computed from the rules, so ranges beyond the horizon work."""
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        events: list[CalendarEvent] = []
        for collection in collections(self.coordinator.data.rules, start, end):
            # An all-day event starts at local midnight; skip one that starts at or after the range end.
            if dt_util.start_of_local_day(collection.date) >= end_date:
                continue
            events.append(_event(collection))
        return events
