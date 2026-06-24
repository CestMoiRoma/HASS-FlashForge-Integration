"""Tests for the Flashforge config flow."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.flashforge.const import (
    API_TYPE_NEW,
    CONF_API_TYPE,
    CONF_CHECK_CODE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from custom_components.flashforge.new_api import NewApiAuthError

from . import get_schema_default, get_schema_suggested, init_integration


async def _legacy_form(hass: HomeAssistant) -> dict:
    """Open the menu and advance to the legacy printer form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "legacy"}
    )


@pytest.mark.asyncio
async def test_user_flow(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test the manual user flow."""
    result = await _legacy_form(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "legacy"
    assert not result["errors"]
    schema = result["data_schema"].schema
    assert get_schema_default(schema, CONF_PORT) == 8899

    # Create the config entry and setup device.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 8899,
        },
    )

    assert result["data"][CONF_IP_ADDRESS] == "127.0.0.1"
    assert result["data"][CONF_PORT] == 8899
    assert result["data"][CONF_SERIAL_NUMBER] == "SNADVA1234567"
    assert result["title"] == "Adventurer4"
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].unique_id == "SNADVA1234567"


@pytest.mark.asyncio
async def test_user_flow_auto_discover(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    mock_printer_discovery: MagicMock,
):
    """Test the auto discovery in manual user flow."""
    # User leaved empty form fields to trigger auto discover.
    result = await _legacy_form(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Assert that we found mocked printer.
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"] == {
        "machine_name": "Adventurer4",
        "ip_addr": "192.168.0.64",
    }
    assert result["step_id"] == "auto_confirm"
    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0]["flow_id"] == result["flow_id"]
    assert progress[0]["context"]["confirm_only"] is True

    # User confirm to add this device.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    # Assert everything is ok.
    assert result["data"][CONF_IP_ADDRESS] == "192.168.0.64"
    assert result["data"][CONF_PORT] == 8899
    assert result["data"][CONF_SERIAL_NUMBER] == "SNADVA1234567"
    assert result["title"] == "Adventurer4"
    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_auto_discover_no_devices(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    mock_printer_discovery: MagicMock,
):
    """Test the auto discovery didn't find any devices."""
    mock_printer_discovery.return_value = []

    # User leaved empty form fields to trigger auto discover.
    result = await _legacy_form(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Assert that no devices discovered.
    assert result["reason"] == "no_devices_found"
    assert result["type"] == FlowResultType.ABORT


@pytest.mark.asyncio
async def test_auto_discover_device_error(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    mock_printer_discovery: MagicMock,
):
    """Test the auto discovery found a device that's not responing as expected."""
    mock_printer_network.connect.side_effect = TimeoutError("timeout")

    # User leaved empty form fields to trigger auto discover.
    result = await _legacy_form(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Assert that no devices discovered.
    assert result["reason"] == "no_devices_found"
    assert result["type"] == FlowResultType.ABORT


@pytest.mark.asyncio
async def test_connection_timeout(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test what happens if there is a connection timeout."""
    mock_printer_network.connect.side_effect = TimeoutError("timeout")

    result = await _legacy_form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 8899,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}
    schema = result["data_schema"].schema
    assert get_schema_suggested(schema, CONF_IP_ADDRESS) == "127.0.0.1"
    assert get_schema_default(schema, CONF_PORT) == 8899


@pytest.mark.asyncio
async def test_connection_error(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test what happens if there is a connection Error."""
    mock_printer_network.connect.side_effect = ConnectionError("conn_error")

    result = await _legacy_form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 8899,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}


@pytest.mark.asyncio
async def test_user_device_exists_abort(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test if device is already configured."""
    await init_integration(hass)

    result = await _legacy_form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 8899,
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_new_api_flow(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_new_api_printer: MagicMock,
):
    """Test adding a newer printer through the HTTP API flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "new_api"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "new_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "192.168.1.20",
            CONF_SERIAL_NUMBER: "SNCR5123",
            CONF_CHECK_CODE: "12345678",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Creator5"
    assert result["data"][CONF_API_TYPE] == API_TYPE_NEW
    assert result["data"][CONF_CHECK_CODE] == "12345678"
    assert result["data"][CONF_SERIAL_NUMBER] == "SNCR5123"
    assert result["data"][CONF_IP_ADDRESS] == "192.168.1.20"


@pytest.mark.asyncio
async def test_new_api_flow_auto_serial(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_new_api_printer: MagicMock,
):
    """Test the serial number is auto-derived when left blank."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "new_api"}
    )

    with patch(
        "custom_components.flashforge.config_flow.fetch_machine_info",
        return_value={"serial": "SNCR5123", "name": "Creator5"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.20",
                CONF_CHECK_CODE: "12345678",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SERIAL_NUMBER] == "SNCR5123"
    assert result["data"][CONF_CHECK_CODE] == "12345678"


@pytest.mark.asyncio
async def test_discover_flow(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_new_api_printer: MagicMock,
):
    """Test discovering a printer pre-fills the new-API form with its serial."""
    discovered = [{"ip": "192.168.1.20", "name": "Creator 5", "serial": "SNCR5123"}]
    with patch(
        "custom_components.flashforge.config_flow.discover_printers",
        return_value=discovered,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        assert result["step_id"] == "discover"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "192.168.1.20"}
        )

    # Landed on the new-API form, pre-filled from the discovery packet.
    assert result["step_id"] == "new_api"
    schema = result["data_schema"].schema
    assert get_schema_suggested(schema, CONF_IP_ADDRESS) == "192.168.1.20"
    assert get_schema_suggested(schema, CONF_SERIAL_NUMBER) == "SNCR5123"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "192.168.1.20",
            CONF_SERIAL_NUMBER: "SNCR5123",
            CONF_CHECK_CODE: "12345678",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TYPE] == API_TYPE_NEW
    assert result["data"][CONF_SERIAL_NUMBER] == "SNCR5123"


@pytest.mark.asyncio
async def test_discover_flow_no_devices(
    enable_custom_integrations,
    hass: HomeAssistant,
):
    """Test the discover flow aborts cleanly when nothing is found."""
    with patch(
        "custom_components.flashforge.config_flow.discover_printers",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_new_api_flow_cannot_connect(
    enable_custom_integrations,
    hass: HomeAssistant,
):
    """Test the new-API flow when the printer can't be reached."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "new_api"}
    )

    with patch(
        "custom_components.flashforge.config_flow.NewApiPrinter"
    ) as mock_printer_cls:
        mock_printer_cls.return_value.connect.side_effect = ConnectionError("nope")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.20",
                CONF_SERIAL_NUMBER: "SNCR5123",
                CONF_CHECK_CODE: "12345678",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_new_api_flow_invalid_check_code(
    enable_custom_integrations,
    hass: HomeAssistant,
):
    """Test a rejected Check Code shows the dedicated invalid_auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "new_api"}
    )

    with patch(
        "custom_components.flashforge.config_flow.NewApiPrinter"
    ) as mock_printer_cls:
        mock_printer_cls.return_value.connect.side_effect = NewApiAuthError("nope")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.20",
                CONF_SERIAL_NUMBER: "SNCR5123",
                CONF_CHECK_CODE: "wrong",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_reconfigure_new_api(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_new_api_printer: MagicMock,
):
    """Test reconfiguring a new-API printer updates its connection details."""
    entry = MockConfigEntry(
        title="Creator5",
        domain=DOMAIN,
        unique_id="SNCR5123",
        data={
            CONF_API_TYPE: API_TYPE_NEW,
            CONF_IP_ADDRESS: "192.168.1.20",
            CONF_PORT: 8898,
            CONF_SERIAL_NUMBER: "SNCR5123",
            CONF_CHECK_CODE: "old12345",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "192.168.1.50",
            CONF_SERIAL_NUMBER: "SNCR5123",
            CONF_CHECK_CODE: "new67890",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.50"
    assert entry.data[CONF_CHECK_CODE] == "new67890"


@pytest.mark.asyncio
async def test_reauth_flow(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_new_api_printer: MagicMock,
):
    """Test re-auth lets the user supply a new Check Code."""
    entry = MockConfigEntry(
        title="Creator5",
        domain=DOMAIN,
        unique_id="SNCR5123",
        data={
            CONF_API_TYPE: API_TYPE_NEW,
            CONF_IP_ADDRESS: "192.168.1.20",
            CONF_PORT: 8898,
            CONF_SERIAL_NUMBER: "SNCR5123",
            CONF_CHECK_CODE: "old12345",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CHECK_CODE: "new67890"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_CHECK_CODE] == "new67890"


@pytest.mark.asyncio
async def test_unload_integration(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test of unload integration."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
async def test_printer_not_responding(
    enable_custom_integrations,  # type: ignore
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
):
    """Test if printer not responding during setup."""
    mock_printer_network.connect.side_effect = ConnectionError("conn_error")
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY

    mock_printer_network.connect.side_effect = TimeoutError("timeout")
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
