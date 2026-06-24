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
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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


def _first_tool_target(handler: ToolHandler) -> float | None:
    """Return the target temperature of the first tool in a handler, if any."""
    tool = handler.get()
    return tool.target if tool is not None else None


@dataclass(frozen=True)
class FlashforgeNumberEntityDescription(NumberEntityDescription):
    """Number entity description with value/set helpers."""

    value_fnc: Callable[[NewApiPrinter], float | None] | None = None
    set_fnc: Callable[[NewApiPrinter, float], Awaitable[None]] | None = None
    requires_printing: bool = False


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
        value_fnc=lambda printer: _first_tool_target(printer.extruder_tools),
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
        value_fnc=lambda printer: _first_tool_target(printer.bed_tools),
        set_fnc=lambda printer, value: printer.set_bed_temp(value),
    ),
    FlashforgeNumberEntityDescription(
        key="cooling_fan",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        mode=NumberMode.SLIDER,
        requires_printing=True,
        value_fnc=lambda printer: printer.cooling_fan_speed,
        set_fnc=lambda printer, value: printer.set_cooling_fan(int(value)),
    ),
    FlashforgeNumberEntityDescription(
        key="chamber_fan",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        mode=NumberMode.SLIDER,
        requires_printing=True,
        value_fnc=lambda printer: printer.chamber_fan_speed,
        set_fnc=lambda printer, value: printer.set_chamber_fan(int(value)),
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
    def available(self) -> bool:
        """Fan controls only work while a print is running."""
        if not super().available:
            return False
        if self.entity_description.requires_printing:
            return bool(getattr(self.coordinator.printer, "is_printing", False))
        return True

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
