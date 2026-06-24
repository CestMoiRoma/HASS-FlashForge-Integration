"""Target-temperature number entities for newer FlashForge printers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .new_api import NewApiPrinter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ffpp.Printer import ToolHandler
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data_update_coordinator import FlashForgeDataUpdateCoordinator


def _tool_target(handler: ToolHandler, name: str) -> float | None:
    """Return the target temperature of a named tool, if present."""
    tool = handler.get(name)
    return tool.target if tool is not None else None


@dataclass(frozen=True)
class FlashforgeNumberEntityDescription(NumberEntityDescription):
    """Number entity description with value/set helpers."""

    value_fnc: Callable[[NewApiPrinter], float | None] | None = None
    set_fnc: Callable[[NewApiPrinter, float], Awaitable[None]] | None = None


NUMBERS: tuple[FlashforgeNumberEntityDescription, ...] = (
    FlashforgeNumberEntityDescription(
        key="nozzle_target",
        icon="mdi:printer-3d-nozzle-heat",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=300,
        native_step=5,
        mode=NumberMode.BOX,
        value_fnc=lambda printer: _tool_target(printer.extruder_tools, "right"),
        set_fnc=lambda printer, value: printer.set_extruder_temp(value),
    ),
    FlashforgeNumberEntityDescription(
        key="bed_target",
        icon="mdi:radiator",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=120,
        native_step=5,
        mode=NumberMode.BOX,
        value_fnc=lambda printer: _tool_target(printer.bed_tools, "bed"),
        set_fnc=lambda printer, value: printer.set_bed_temp(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FlashForge temperature numbers for newer printers."""
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if isinstance(coordinator.printer, NewApiPrinter):
        async_add_entities(
            FlashForgeNumber(coordinator, description) for description in NUMBERS
        )


class FlashForgeNumber(CoordinatorEntity, NumberEntity):
    """A settable target temperature on a newer FlashForge printer."""

    _attr_has_entity_name = True
    entity_description: FlashforgeNumberEntityDescription

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        description: FlashforgeNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self._attr_name = description.key.replace("_", " ").title()
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        if self.entity_description.value_fnc is None:
            return None
        return self.entity_description.value_fnc(self.coordinator.printer)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new target temperature on the printer."""
        if self.entity_description.set_fnc is None:
            return
        await self.entity_description.set_fnc(self.coordinator.printer, value)
        await self.coordinator.async_request_refresh()
