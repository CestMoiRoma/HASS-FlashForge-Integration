"""Binary sensors for newer FlashForge printers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .new_api import NewApiPrinter

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data_update_coordinator import FlashForgeDataUpdateCoordinator


@dataclass(frozen=True)
class FlashforgeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value function."""

    value_fnc: Callable[[NewApiPrinter], bool] | None = None


BINARY_SENSORS: tuple[FlashforgeBinarySensorEntityDescription, ...] = (
    FlashforgeBinarySensorEntityDescription(
        key="printing",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fnc=lambda printer: printer.is_printing,
    ),
    FlashforgeBinarySensorEntityDescription(
        key="paused",
        icon="mdi:pause",
        value_fnc=lambda printer: printer.is_paused,
    ),
    FlashforgeBinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fnc=lambda printer: printer.door_open,
    ),
    FlashforgeBinarySensorEntityDescription(
        key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fnc=lambda printer: printer.has_error,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FlashForge binary sensors for newer printers."""
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if isinstance(coordinator.printer, NewApiPrinter):
        async_add_entities(
            FlashForgeBinarySensor(coordinator, description)
            for description in BINARY_SENSORS
        )


class FlashForgeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a FlashForge binary sensor."""

    _attr_has_entity_name = True
    entity_description: FlashforgeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        description: FlashforgeBinarySensorEntityDescription,
    ) -> None:
        """Initialize a new FlashForge binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self._attr_name = description.key.replace("_", " ").title()
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.entity_description.value_fnc is None:
            return None
        return self.entity_description.value_fnc(self.coordinator.printer)
