"""Print-file thumbnail image entity for newer FlashForge printers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.image import ImageEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .new_api import NewApiPrinter

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data_update_coordinator import FlashForgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the print-file thumbnail image entity for newer printers."""
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Thumbnails are only available through the newer HTTP API (see issue #113).
    if isinstance(coordinator.printer, NewApiPrinter):
        async_add_entities([FlashForgeThumbnail(hass, coordinator)])


class FlashForgeThumbnail(CoordinatorEntity, ImageEntity):
    """Thumbnail of the file currently being printed (see issue #113)."""

    _attr_has_entity_name = True
    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: FlashForgeDataUpdateCoordinator
    ) -> None:
        """Initialize the thumbnail image entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_thumbnail"
        self._attr_name = "Print thumbnail"
        self._attr_icon = "mdi:image"
        self._attr_device_info = coordinator.device_info
        self._current_file = coordinator.printer.job_file
        self._cached_image: bytes | None = None
        if self._current_file:
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Invalidate the cached image when the print file changes."""
        job_file = self.coordinator.printer.job_file
        if job_file != self._current_file:
            self._current_file = job_file
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return the thumbnail bytes for the current print file."""
        if not self._current_file:
            return None
        if self._cached_image is None:
            try:
                self._cached_image = await self.coordinator.printer.get_thumbnail()
            except (TimeoutError, ConnectionError):
                return None
        return self._cached_image
