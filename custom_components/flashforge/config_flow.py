"""Config flow for Flashforge."""

from typing import Any

import voluptuous as vol
from ffpp import Discovery
from ffpp.Printer import Printer
from homeassistant import config_entries
from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_TYPE_LEGACY,
    API_TYPE_NEW,
    CONF_API_TYPE,
    CONF_CHECK_CODE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    LEGACY_PORT,
    NEW_API_PORT,
)
from .new_api import NewApiPrinter


class FlashForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow."""

    VERSION = 1

    ip_addr: str | None
    port: int
    serial: str
    machine_type: str
    printer: Printer

    async def async_step_user(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose which kind of printer to add."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["legacy", "new_api"],
        )

    async def async_step_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a legacy printer over the M-code protocol (port 8899)."""
        errors = {}
        self.port = LEGACY_PORT
        self.ip_addr = None

        if user_input is not None:
            if CONF_IP_ADDRESS not in user_input:
                # Try to discover printers on network and
                # then show the confirm form.
                return await self.async_step_auto()

            self.ip_addr = user_input[CONF_IP_ADDRESS]
            self.port = user_input[CONF_PORT]

            try:
                await self._get_printer_info(self.hass, user_input)

                return self._async_create_entry()
            except (TimeoutError, ConnectionError):
                errors[CONF_IP_ADDRESS] = "cannot_connect"

        return self._async_show_form(errors=errors)

    async def async_step_new_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        Add a newer printer over the HTTP API (port 8898 + Check Code).

        Covers the Adventurer 5M / 5M Pro, AD5X and Creator series, which
        require LAN mode and an 8-digit Check Code from the printer screen.
        """
        errors = {}

        if user_input is not None:
            ip_addr = user_input[CONF_IP_ADDRESS]
            serial = user_input[CONF_SERIAL_NUMBER]
            check_code = user_input[CONF_CHECK_CODE]
            printer = NewApiPrinter(
                ip_addr, serial, check_code, async_get_clientsession(self.hass)
            )
            try:
                await printer.connect()
            except (TimeoutError, ConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                title = printer.machine_name or serial
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_API_TYPE: API_TYPE_NEW,
                        CONF_IP_ADDRESS: ip_addr,
                        CONF_PORT: NEW_API_PORT,
                        CONF_SERIAL_NUMBER: serial,
                        CONF_CHECK_CODE: check_code,
                    },
                )

        # Pre-fill the IP by trying to discover a printer on the network. This
        # is best-effort: if nothing answers the user just types the address.
        suggested = dict(user_input or {})
        if not suggested.get(CONF_IP_ADDRESS):
            discovered_ip = await self._discover_new_ip()
            if discovered_ip:
                suggested[CONF_IP_ADDRESS] = discovered_ip

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_IP_ADDRESS,
                    description={"suggested_value": suggested.get(CONF_IP_ADDRESS)},
                ): str,
                vol.Required(
                    CONF_SERIAL_NUMBER,
                    description={"suggested_value": suggested.get(CONF_SERIAL_NUMBER)},
                ): str,
                vol.Required(
                    CONF_CHECK_CODE,
                    description={"suggested_value": suggested.get(CONF_CHECK_CODE)},
                ): str,
            }
        )
        return self.async_show_form(
            step_id="new_api",
            data_schema=data_schema,
            errors=errors,
        )

    async def _discover_new_ip(self) -> str | None:
        """Best-effort discovery of a printer's IP for the new-API form."""
        try:
            local_ip = await async_get_source_ip(self.hass)
            printers = await Discovery.getPrinters(
                self.hass.loop, limit=1, host_ip=local_ip
            )
        except Exception:  # noqa: BLE001 - discovery is optional, never fatal
            return None
        for _, ip_addr in printers:
            return ip_addr
        return None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update connection details of an existing printer."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_API_TYPE) == API_TYPE_NEW:
            return await self._async_reconfigure_new(entry, user_input)
        return await self._async_reconfigure_legacy(entry, user_input)

    async def _async_reconfigure_new(
        self, entry: config_entries.ConfigEntry, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Reconfigure a new-API printer (IP / serial / Check Code)."""
        errors = {}
        if user_input is not None:
            printer = NewApiPrinter(
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_SERIAL_NUMBER],
                user_input[CONF_CHECK_CODE],
                async_get_clientsession(self.hass),
            )
            try:
                await printer.connect()
            except (TimeoutError, ConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_SERIAL_NUMBER])
                self._abort_if_unique_id_mismatch(reason="wrong_printer")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                        CONF_SERIAL_NUMBER: user_input[CONF_SERIAL_NUMBER],
                        CONF_CHECK_CODE: user_input[CONF_CHECK_CODE],
                    },
                )

        current = user_input or entry.data
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_IP_ADDRESS,
                    description={"suggested_value": current.get(CONF_IP_ADDRESS)},
                ): str,
                vol.Required(
                    CONF_SERIAL_NUMBER,
                    description={"suggested_value": current.get(CONF_SERIAL_NUMBER)},
                ): str,
                vol.Required(
                    CONF_CHECK_CODE,
                    description={"suggested_value": current.get(CONF_CHECK_CODE)},
                ): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )

    async def _async_reconfigure_legacy(
        self, entry: config_entries.ConfigEntry, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Reconfigure a legacy printer (IP / port)."""
        errors = {}
        if user_input is not None:
            printer = Printer(user_input[CONF_IP_ADDRESS], user_input[CONF_PORT])
            try:
                await printer.connect()
            except (TimeoutError, ConnectionError):
                errors[CONF_IP_ADDRESS] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                )

        current = user_input or entry.data
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_IP_ADDRESS,
                    description={"suggested_value": current.get(CONF_IP_ADDRESS)},
                ): str,
                vol.Required(
                    CONF_PORT, default=current.get(CONF_PORT, LEGACY_PORT)
                ): cv.port,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )

    async def async_step_auto(self) -> ConfigFlowResult:
        """Try to discover ip of printer and return a confirm form."""
        ip = None
        port = LEGACY_PORT
        local_ip = await async_get_source_ip(self.hass)
        discovered_printers = await Discovery.getPrinters(
            self.hass.loop,
            limit=1,
            host_ip=local_ip,
        )
        # Get the first discovered printer ip
        for _, ip_addr in discovered_printers:
            ip = ip_addr
            break

        if ip is None:
            return self.async_abort(reason="no_devices_found")

        try:
            await self._get_printer_info(
                self.hass, {CONF_IP_ADDRESS: ip, CONF_PORT: port}
            )
        except (TimeoutError, ConnectionError):
            return self.async_abort(reason="no_devices_found")

        self._set_confirm_only()
        title = self.printer.machine_name or self.printer.serial or ""
        return self.async_show_form(
            step_id="auto_confirm",
            description_placeholders={
                "machine_name": title,
                "ip_addr": ip,
            },
        )

    async def async_step_auto_confirm(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User confirmed to add device to Home Assistant."""
        return self._async_create_entry()

    @callback
    def _async_show_form(
        self,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Create and show the form for user."""
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_IP_ADDRESS,
                    description={"suggested_value": self.ip_addr},
                ): str,
                vol.Optional(CONF_PORT, default=self.port): cv.port,
            }
        )

        return self.async_show_form(
            step_id="legacy",
            data_schema=data_schema,
            errors=errors or {},
        )

    async def _get_printer_info(self, hass: HomeAssistant, user_input: dict) -> None:  # noqa: ARG002
        """Try to get info from given ip."""
        self.ip_addr = user_input[CONF_IP_ADDRESS]
        self.port = user_input[CONF_PORT]
        self.printer = Printer(self.ip_addr, self.port)

        await self.printer.connect()

        if self.printer.serial is not None:
            await self.async_set_unique_id(self.printer.serial)

        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: self.ip_addr, CONF_PORT: self.port}
        )

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        """Create config entry."""
        title = self.printer.machine_name or self.printer.serial or ""
        return self.async_create_entry(
            title=title,
            data={
                CONF_API_TYPE: API_TYPE_LEGACY,
                CONF_IP_ADDRESS: self.ip_addr,
                CONF_PORT: self.port,
                CONF_SERIAL_NUMBER: self.printer.serial,
            },
        )
