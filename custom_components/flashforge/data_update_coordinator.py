"""DataUpdateCoordinator for flashforge integration."""

import logging
from datetime import timedelta

from ffpp.Printer import ConnectionStatus, Printer
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    EVENT_PRINT_FINISHED,
    EVENT_PRINTER_ERROR,
    MAX_FAILED_UPDATES,
    SCAN_INTERVAL,
    STATUS_COMPLETED,
)
from .new_api import NewApiAuthError, NewApiPrinter

_LOGGER = logging.getLogger(__name__)


class FlashForgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FlashForgeprinter data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        printer: Printer | NewApiPrinter,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DEFAULT_NAME}-{config_entry.entry_id}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            update_method=self.async_update_data,
        )
        self.config_entry = config_entry
        self.printer = printer
        self.data = {
            "status": None,
        }
        self._last_status: str | None = None
        self._last_error = False

    async def async_update_data(self) -> dict[str, list[str] | str | None]:
        """
        Update data via API.

        Retry the request up to ``MAX_FAILED_UPDATES`` times on connection
        errors before giving up, so a single dropped packet does not mark the
        printer as unavailable.
        """
        last_err: Exception | None = None
        for _ in range(MAX_FAILED_UPDATES):
            try:
                await self.printer.update()
                files = await self.printer.network.sendGetFileNames()
            except NewApiAuthError as err:
                # The Check Code was rejected (e.g. regenerated on the printer).
                # Trigger Home Assistant's re-auth flow instead of retrying.
                raise ConfigEntryAuthFailed(err) from err
            except (TimeoutError, ConnectionError) as err:
                last_err = err
                continue

            files = [f.removeprefix("/data/") for f in files] if files else []
            self._fire_state_events()
            return {"status": self.printer.machine_status, "files": files}

        raise UpdateFailed(last_err)

    def _fire_state_events(self) -> None:
        """Fire bus events on print-finished and error transitions."""
        status = self.printer.machine_status
        if status != self._last_status:
            if status == STATUS_COMPLETED and self._last_status is not None:
                self.hass.bus.async_fire(EVENT_PRINT_FINISHED, self._event_data())
            self._last_status = status

        has_error = bool(getattr(self.printer, "has_error", False))
        if has_error and not self._last_error:
            self.hass.bus.async_fire(EVENT_PRINTER_ERROR, self._event_data())
        self._last_error = has_error

    def _event_data(self) -> dict[str, str | None]:
        """Build the payload shared by the fired events."""
        return {
            "device_id": self.config_entry.unique_id,
            "name": self.printer.machine_name or self.config_entry.title,
            "file": self.printer.job_file,
            "status": self.printer.machine_status,
        }

    async def async_config_entry_first_refresh(self) -> None:
        """Connect to printer and update with machine info."""
        self.printer.connected = ConnectionStatus.DISCONNECTED
        await self.printer.connect()

        return await super().async_config_entry_first_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        unique_id = self.config_entry.unique_id or ""
        model = self.printer.machine_type
        name = self.printer.machine_name or self.config_entry.title or DEFAULT_NAME
        firmware = self.printer.firmware
        sn = self.printer.serial
        mac = self.printer.mac_address

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="FlashForge",
            model=model,
            name=name,
            sw_version=firmware,
            serial_number=sn,
            hw_version=mac,
        )
