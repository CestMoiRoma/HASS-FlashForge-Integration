"""Support for flashforge selects."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .new_api import FILTRATION_MODES, NewApiPrinter

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data_update_coordinator import FlashForgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FlashForge select based on a config entry."""
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = [FlashForgeSelect(coordinator)]

    # Filtration / exhaust-fan control is only available on newer printers that
    # report the capability (see issue #90).
    printer = coordinator.printer
    if isinstance(printer, NewApiPrinter) and printer.filtration_control:
        entities.append(FlashForgeFiltrationSelect(coordinator))

    async_add_entities(entities)


class FlashForgeSelect(CoordinatorEntity, SelectEntity):
    """Representation of a demo select entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        options: list[str] | None = None,
    ) -> None:
        """Initialize the Demo select entity."""
        super().__init__(coordinator)
        options = options or []
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_select"
        self._attr_current_option = options[0] if options else None
        self._attr_icon = "mdi:file-cad"
        self._attr_name = "File list"
        self._attr_options = options
        self._attr_device_info = coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_options = self.coordinator.data["files"]
        except KeyError:
            self._attr_options = []
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()


class FlashForgeFiltrationSelect(CoordinatorEntity, SelectEntity):
    """Filtration / exhaust-fan mode control for newer printers."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: FlashForgeDataUpdateCoordinator) -> None:
        """Initialize the filtration select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_filtration"
        self._attr_icon = "mdi:air-filter"
        self._attr_name = "Filtration"
        self._attr_options = list(FILTRATION_MODES)
        self._attr_current_option = coordinator.printer.filtration_mode
        self._attr_device_info = coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.coordinator.printer.filtration_mode
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the filtration mode on the printer."""
        await self.coordinator.printer.set_filtration(option)
        self._attr_current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
