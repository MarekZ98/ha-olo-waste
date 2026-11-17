"""Next pickup date per waste kind, plus the next pickup of any kind."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import OloConfigEntry
from .calendar import device_info
from .const import KIND_ICONS, KIND_NAMES_SK
from .coordinator import OloCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one sensor per kind plus `next_pickup`."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [OloKindSensor(coordinator, entry, kind) for kind in coordinator.data.kinds]
    entities.append(OloNextPickupSensor(coordinator, entry))
    async_add_entities(entities)


def _days_until(value: date | None) -> int | None:
    return None if value is None else (value - dt_util.now().date()).days


class _OloSensor(CoordinatorEntity[OloCoordinator], SensorEntity):
    """Shared setup of the OLO sensors."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: OloCoordinator, entry: OloConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry, coordinator.address)


class OloKindSensor(_OloSensor):
    """Next pickup date of one waste kind."""

    def __init__(self, coordinator: OloCoordinator, entry: OloConfigEntry, kind: str) -> None:
        super().__init__(coordinator, entry, kind)
        self._kind = kind
        self._attr_icon = KIND_ICONS.get(kind)

    @property
    def native_value(self) -> date | None:
        today = dt_util.now().date()
        return next(
            (c.date for c in self.coordinator.data.collections if c.kind == self._kind and c.date >= today),
            None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"days_until": _days_until(self.native_value)}


class OloNextPickupSensor(_OloSensor):
    """Next pickup date of any kind."""

    _attr_icon = "mdi:delete-clock"

    def __init__(self, coordinator: OloCoordinator, entry: OloConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_pickup")

    @property
    def native_value(self) -> date | None:
        today = dt_util.now().date()
        return next((c.date for c in self.coordinator.data.collections if c.date >= today), None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        value = self.native_value
        kinds = [KIND_NAMES_SK.get(c.kind, c.kind) for c in self.coordinator.data.collections if c.date == value]
        return {"kinds": kinds, "days_until": _days_until(value)}
