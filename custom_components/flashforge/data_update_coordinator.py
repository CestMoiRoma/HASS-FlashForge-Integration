"""DataUpdateCoordinator for flashforge integration."""

import logging
from datetime import timedelta

from ffpp.Printer import ConnectionStatus, Printer
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DOMAIN, MAX_FAILED_UPDATES, SCAN_INTERVAL
from .new_api import NewApiPrinter

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
            except (TimeoutError, ConnectionError) as err:
                last_err = err
                continue

            files = [f.removeprefix("/data/") for f in files] if files else []
            return {"status": self.printer.machine_status, "files": files}

        raise UpdateFailed(last_err)

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
        name = self.printer.machine_name or self.config_entry.title
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
