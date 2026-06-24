"""
Client for the newer FlashForge LAN HTTP API (port 8898).

Newer FlashForge printers (Adventurer 5M / 5M Pro, AD5X and the Creator series)
no longer expose the open M-code TCP service on port 8899. Instead they require
*LAN mode* to be enabled on the printer together with an 8-digit *Check Code*,
and they speak a JSON HTTP API on port 8898.

This module provides :class:`NewApiPrinter` and :class:`NewApiNetwork`, which
mirror the public interface of :class:`ffpp.Printer.Printer` and its ``Network``
object. Because the rest of the integration (coordinator, sensors, buttons,
light, camera and services) only talks to that interface, everything keeps
working unchanged regardless of which protocol a given printer speaks.

Field names, command names and payloads follow the unofficial FlashForge API
documentation (https://github.com/Parallel-7/flashforge-api-docs).
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from ffpp.Network import Network
from ffpp.Printer import ConnectionStatus, ToolHandler, temperatures

if TYPE_CHECKING:
    from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

API_PORT = 8898
# Control commands (e.g. setting temperatures) still use the M-code service on
# the legacy TCP port, which newer printers keep open for control.
LEGACY_TCP_PORT = 8899
CAMERA_PORT = 8080
REQUEST_TIMEOUT = 10
_HTTP_OK = 200

# Endpoints on the port-8898 HTTP API.
_ENDPOINT_DETAIL = "/detail"
_ENDPOINT_CONTROL = "/control"
_ENDPOINT_PRODUCT = "/product"
_ENDPOINT_GCODE_LIST = "/gcodeList"
_ENDPOINT_GCODE_PRINT = "/printGcode"
_ENDPOINT_GCODE_THUMB = "/gcodeThumb"

# ``payload.cmd`` values used by the ``/control`` endpoint.
_CMD_JOB_CONTROL = "jobCtl_cmd"
_CMD_LIGHT_CONTROL = "lightControl_cmd"
_CMD_CIRCULATE_CONTROL = "circulateCtl_cmd"
_CMD_STATE_CONTROL = "stateCtrl_cmd"

# Filtration / exhaust-fan modes exposed to the select entity (see issue #90).
FILTRATION_OFF = "off"
FILTRATION_INTERNAL = "internal"
FILTRATION_EXTERNAL = "external"
FILTRATION_MODES = (FILTRATION_OFF, FILTRATION_INTERNAL, FILTRATION_EXTERNAL)

# Map the raw lower-case status reported by the new API to the legacy upper-case
# ``MachineStatus`` names, so existing consumers keep working unchanged (for
# example the ``print_file`` service which only prints when status is "READY").
STATUS_MAP = {
    "ready": "READY",
    "busy": "BUSY",
    "heating": "HEATING",
    "calibrate_doing": "CALIBRATING",
    "printing": "BUILDING_FROM_SD",
    "pausing": "PAUSING",
    "paused": "PAUSED",
    "completed": "BUILDING_COMPLETED",
    "canceling": "CANCELING",
    "cancel": "CANCELLED",
    "error": "ERROR",
}

# Firmware-reported PID -> human readable model name.
MODEL_BY_PID = {
    35: "Adventurer 5M",
    36: "Adventurer 5M Pro",
    38: "AD5X",
}


class NewApiError(ConnectionError):
    """Raised when the printer answers with a non-OK HTTP status or error code."""


class NewApiNetwork:
    """
    Async JSON client for the FlashForge port-8898 HTTP API.

    Mirrors the subset of :class:`ffpp.Network.Network` that the integration
    uses, so it is a drop-in replacement for legacy printers.
    """

    def __init__(
        self, ip: str, serial: str, check_code: str, session: ClientSession
    ) -> None:
        """Initialize the client with printer address and credentials."""
        self.ip = ip
        self.port = API_PORT
        self._serial = serial
        self._check_code = check_code
        self._session = session
        self._base = f"http://{ip}:{API_PORT}"
        self._camera_stream_url: str | None = None

    async def _post(
        self, endpoint: str, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST an authenticated request and return the decoded JSON body."""
        payload: dict[str, Any] = {
            "serialNumber": self._serial,
            "checkCode": self._check_code,
        }
        if extra:
            payload.update(extra)

        try:
            async with self._session.post(
                f"{self._base}{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status != _HTTP_OK:
                    msg = f"{endpoint} returned HTTP {response.status}"
                    raise NewApiError(msg)
                data: dict[str, Any] = await response.json(content_type=None)
        except TimeoutError:
            raise
        except aiohttp.ClientError as err:
            raise ConnectionError(str(err)) from err

        code = data.get("code")
        if code not in (0, None):
            msg = f"{endpoint} returned code {code}: {data.get('message')}"
            raise NewApiError(msg)
        return data

    async def getDetail(self) -> dict[str, Any]:  # noqa: N802 - mirror ffpp API
        """Return the ``detail`` object describing the current printer state."""
        data = await self._post(_ENDPOINT_DETAIL)
        detail: dict[str, Any] = data.get("detail", {})
        self._camera_stream_url = detail.get("cameraStreamUrl") or None
        return detail

    async def _send_control(self, cmd: str, args: dict[str, Any]) -> bool:
        """Send a ``/control`` command with the given ``cmd`` and ``args``."""
        await self._post(_ENDPOINT_CONTROL, {"payload": {"cmd": cmd, "args": args}})
        return True

    async def sendPauseRequest(self) -> bool:  # noqa: N802 - mirror ffpp API
        """Pause the current print."""
        return await self._send_control(
            _CMD_JOB_CONTROL, {"jobID": "", "action": "pause"}
        )

    async def sendContinueRequest(self) -> bool:  # noqa: N802 - mirror ffpp API
        """Resume the current print."""
        return await self._send_control(
            _CMD_JOB_CONTROL, {"jobID": "", "action": "continue"}
        )

    async def sendAbortRequest(self) -> bool:  # noqa: N802 - mirror ffpp API
        """Cancel the current print."""
        return await self._send_control(
            _CMD_JOB_CONTROL, {"jobID": "", "action": "cancel"}
        )

    async def sendSetLedState(self, state: bool) -> bool:  # noqa: FBT001, N802
        """Turn the chamber LED on or off."""
        return await self._send_control(
            _CMD_LIGHT_CONTROL, {"status": "open" if state else "close"}
        )

    async def sendPrintRequest(self, file: str) -> bool:  # noqa: N802 - mirror ffpp
        """Start printing a file already stored on the printer."""
        await self._post(
            _ENDPOINT_GCODE_PRINT,
            {"fileName": file, "levelingBeforePrint": False},
        )
        return True

    async def sendGetFileNames(self) -> list[str]:  # noqa: N802 - mirror ffpp API
        """Return the list of g-code files stored on the printer."""
        data = await self._post(_ENDPOINT_GCODE_LIST)
        raw = data.get("gcodeList") or []
        files: list[str] = []
        for entry in raw:
            if isinstance(entry, str):
                files.append(entry)
            elif isinstance(entry, dict) and entry.get("gcodeFileName"):
                files.append(entry["gcodeFileName"])
        return files

    async def getCameraStream(self) -> str:  # noqa: N802 - mirror ffpp API
        """Return the MJPEG camera stream URL."""
        return (
            self._camera_stream_url or f"http://{self.ip}:{CAMERA_PORT}/?action=stream"
        )

    async def getProduct(self) -> dict[str, Any]:  # noqa: N802 - mirror ffpp API
        """Return the ``product`` object describing the printer's capabilities."""
        data = await self._post(_ENDPOINT_PRODUCT)
        return data.get("product", {})

    async def setFiltration(  # noqa: N802 - mirror ffpp API
        self, *, internal: bool, external: bool
    ) -> bool:
        """Set the internal/external filtration (exhaust fan) state."""
        return await self._send_control(
            _CMD_CIRCULATE_CONTROL,
            {
                "internal": "open" if internal else "close",
                "external": "open" if external else "close",
            },
        )

    async def getThumbnail(self, file_name: str) -> bytes | None:  # noqa: N802
        """Return the PNG thumbnail for ``file_name`` as raw bytes, if any."""
        data = await self._post(_ENDPOINT_GCODE_THUMB, {"fileName": file_name})
        image_data = data.get("imageData")
        if not image_data:
            return None
        return base64.b64decode(image_data)

    async def sendClearPlatform(self) -> bool:  # noqa: N802 - mirror ffpp API
        """Tell the printer the build platform has been cleared."""
        return await self._send_control(
            _CMD_STATE_CONTROL, {"action": "setClearPlatform"}
        )


class NewApiPrinter:
    """
    Adapter exposing the :class:`ffpp.Printer.Printer` interface over HTTP.

    Only the attributes and methods consumed by the integration are
    implemented. Reading is done through :meth:`update`, which fetches
    ``/detail`` once and maps the response onto ffpp-compatible properties.
    """

    def __init__(
        self, ip: str, serial: str, check_code: str, session: ClientSession
    ) -> None:
        """Initialize the printer adapter."""
        self.connected: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self.network = NewApiNetwork(ip, serial, check_code, session)
        self._serial = serial
        self._ip = ip
        # Lazily created M-code transport for control commands (port 8899).
        self._tcp: Network | None = None
        self.extruder_tools = ToolHandler()
        self.bed_tools = ToolHandler()

        self._machine_type: str | None = None
        self._machine_name: str | None = None
        self._firmware: str | None = None
        self._mac_address: str | None = None
        self._machine_status: str | None = None
        self._status: str | None = None
        self._move_mode: str | None = None
        self._led = False
        self._job_file: str | None = None
        self._print_percent: int | None = None
        self._print_layer: int | None = None
        self._job_layers: int | None = None
        self._internal_fan = False
        self._external_fan = False
        # Extra telemetry (quick-win sensors).
        self._estimated_time: int | None = None
        self._print_duration: int | None = None
        self._chamber_temp: float | None = None
        self._chamber_target: float | None = None
        self._nozzle_size: str | None = None
        self._filament_type: str | None = None
        self._current_print_speed: int | None = None
        self._print_speed_adjust: int | None = None
        self._error_code: str | None = None
        self._free_disk_space: float | None = None
        self._cumulative_filament: float | None = None
        self._cumulative_print_time: int | None = None
        self._door_open = False
        # Capability flags, populated from /product on connect.
        self.filtration_control = False

    @property
    def machine_type(self) -> str | None:
        """Model name of the printer."""
        return self._machine_type

    @property
    def machine_name(self) -> str | None:
        """User-defined printer name."""
        return self._machine_name

    @property
    def firmware(self) -> str | None:
        """Firmware version string."""
        return self._firmware

    @property
    def serial(self) -> str:
        """Serial number used to authenticate against the printer."""
        return self._serial

    @property
    def mac_address(self) -> str | None:
        """MAC address of the printer, if reported."""
        return self._mac_address

    @property
    def machine_status(self) -> str | None:
        """Legacy-style upper-case machine status (e.g. ``READY``)."""
        return self._machine_status

    @property
    def move_mode(self) -> str | None:
        """Synthesised move mode (``READY`` / ``MOVING``)."""
        return self._move_mode

    @property
    def status(self) -> str | None:
        """Raw status string reported by the new API (e.g. ``printing``)."""
        return self._status

    @property
    def led(self) -> bool:
        """Whether the chamber LED is on."""
        return self._led

    @property
    def job_file(self) -> str | None:
        """Name of the file currently being printed."""
        return self._job_file

    @property
    def print_percent(self) -> int | None:
        """Print progress as a whole-number percentage."""
        return self._print_percent

    @property
    def print_layer(self) -> int | None:
        """Layer currently being printed."""
        return self._print_layer

    @property
    def job_layers(self) -> int | None:
        """Total number of layers in the current job."""
        return self._job_layers

    @property
    def filtration_mode(self) -> str:
        """Current filtration mode (``off`` / ``internal`` / ``external``)."""
        if self._external_fan:
            return FILTRATION_EXTERNAL
        if self._internal_fan:
            return FILTRATION_INTERNAL
        return FILTRATION_OFF

    @property
    def estimated_time(self) -> int | None:
        """Estimated time remaining for the current job, in seconds."""
        return self._estimated_time

    @property
    def print_duration(self) -> int | None:
        """Elapsed print time of the current job, in seconds."""
        return self._print_duration

    @property
    def chamber_temp(self) -> float | None:
        """Current chamber temperature."""
        return self._chamber_temp

    @property
    def chamber_target(self) -> float | None:
        """Target chamber temperature."""
        return self._chamber_target

    @property
    def nozzle_size(self) -> str | None:
        """Installed nozzle model / size."""
        return self._nozzle_size

    @property
    def filament_type(self) -> str | None:
        """Loaded filament type for the right/primary extruder."""
        return self._filament_type

    @property
    def current_print_speed(self) -> int | None:
        """Current print speed reported by the printer."""
        return self._current_print_speed

    @property
    def print_speed_adjust(self) -> int | None:
        """Print speed override, as a percentage."""
        return self._print_speed_adjust

    @property
    def error_code(self) -> str | None:
        """Last error code reported by the printer, if any."""
        return self._error_code

    @property
    def free_disk_space(self) -> float | None:
        """Remaining storage space on the printer."""
        return self._free_disk_space

    @property
    def cumulative_filament(self) -> float | None:
        """Lifetime filament used, in metres."""
        return self._cumulative_filament

    @property
    def cumulative_print_time(self) -> int | None:
        """Lifetime print time, in minutes."""
        return self._cumulative_print_time

    @property
    def door_open(self) -> bool:
        """Whether the printer door is open."""
        return self._door_open

    @property
    def is_printing(self) -> bool:
        """Whether a print job is currently running."""
        return (self._status or "").lower() == "printing"

    @property
    def is_paused(self) -> bool:
        """Whether the current job is paused."""
        return (self._status or "").lower() in ("paused", "pausing")

    @property
    def has_error(self) -> bool:
        """Whether the printer is reporting an error."""
        return (self._status or "").lower() == "error" or bool(self._error_code)

    async def connect(self) -> bool:
        """Perform an initial fetch and mark the printer connected."""
        await self.update()
        try:
            product = await self.network.getProduct()
        except (TimeoutError, ConnectionError):
            product = {}
        self.filtration_control = bool(
            product.get("externalFanCtrlState") or product.get("internalFanCtrlState")
        )
        self.connected = ConnectionStatus.CONNECTED
        return True

    async def update(self) -> None:
        """Fetch ``/detail`` and refresh all cached values."""
        detail = await self.network.getDetail()
        self._apply_detail(detail)

    async def setLed(self, state: bool) -> None:  # noqa: FBT001, N802 - mirror ffpp
        """Set the chamber LED state and update the cached value."""
        await self.network.sendSetLedState(state)
        self._led = state

    async def set_filtration(self, mode: str) -> None:
        """Set the filtration mode (``off`` / ``internal`` / ``external``)."""
        internal = mode == FILTRATION_INTERNAL
        external = mode == FILTRATION_EXTERNAL
        await self.network.setFiltration(internal=internal, external=external)
        self._internal_fan = internal
        self._external_fan = external

    async def get_thumbnail(self) -> bytes | None:
        """Return the thumbnail bytes for the current print file, if any."""
        if not self._job_file:
            return None
        return await self.network.getThumbnail(self._job_file)

    async def _send_gcode(self, command: str) -> None:
        """
        Send a single M-code over TCP, wrapped in control acquire/release.

        Newer printers require control to be claimed (``~M601 S1``) before they
        accept commands and released again afterwards (``~M602``).
        """
        if self._tcp is None:
            self._tcp = Network(self._ip, LEGACY_TCP_PORT)
        await self._tcp.sendMessage(
            ["~M601 S1\r\n", f"{command}\r\n", "~M602\r\n"],
        )

    async def set_extruder_temp(self, temperature: float) -> None:
        """Set the target extruder temperature (0 turns the heater off)."""
        await self._send_gcode(f"~M104 S{int(temperature)}")

    async def set_bed_temp(self, temperature: float) -> None:
        """Set the target bed temperature (0 turns the heater off)."""
        await self._send_gcode(f"~M140 S{int(temperature)}")

    def _apply_detail(self, detail: dict[str, Any]) -> None:
        """Map a ``/detail`` response onto the ffpp-compatible properties."""
        raw_status = (detail.get("status") or "").lower()
        self._status = detail.get("status")
        self._machine_status = STATUS_MAP.get(raw_status, detail.get("status"))
        self._move_mode = (
            "MOVING"
            if raw_status in ("printing", "busy", "calibrate_doing", "heating")
            else "READY"
        )
        self._machine_name = detail.get("name")
        self._firmware = detail.get("firmwareVersion")
        self._mac_address = detail.get("macAddr")
        self._machine_type = MODEL_BY_PID.get(detail.get("pid"), "FlashForge (LAN)")
        self._led = (detail.get("lightStatus") or "").lower() == "open"
        self._internal_fan = (detail.get("internalFanStatus") or "").lower() == "open"
        self._external_fan = (detail.get("externalFanStatus") or "").lower() == "open"
        self._job_file = detail.get("printFileName") or None

        progress = detail.get("printProgress")
        self._print_percent = round(progress * 100) if progress is not None else None
        self._print_layer = detail.get("printLayer")
        self._job_layers = detail.get("targetPrintLayer")

        self._estimated_time = detail.get("estimatedTime")
        self._print_duration = detail.get("printDuration")
        self._chamber_temp = detail.get("chamberTemp")
        self._chamber_target = detail.get("chamberTargetTemp")
        self._nozzle_size = detail.get("nozzleModel")
        self._filament_type = detail.get("rightFilamentType")
        self._current_print_speed = detail.get("currentPrintSpeed")
        self._print_speed_adjust = detail.get("printSpeedAdjust")
        self._error_code = detail.get("errorCode") or None
        self._free_disk_space = detail.get("remainingDiskSpace")
        self._cumulative_filament = detail.get("cumulativeFilament")
        self._cumulative_print_time = detail.get("cumulativePrintTime")
        self._door_open = (detail.get("doorStatus") or "").lower() == "open"

        # Rebuild the temperature handlers from the latest reading. Bed and
        # right tool are always present; the left tool only exists on dual /
        # IDEX machines such as the Creator series.
        self.extruder_tools = ToolHandler()
        self.bed_tools = ToolHandler()
        self._add_tool(
            self.bed_tools, "bed", detail.get("platTemp"), detail.get("platTargetTemp")
        )
        self._add_tool(
            self.extruder_tools,
            "right",
            detail.get("rightTemp"),
            detail.get("rightTargetTemp"),
        )
        if detail.get("leftTemp") is not None:
            self._add_tool(
                self.extruder_tools,
                "left",
                detail.get("leftTemp"),
                detail.get("leftTargetTemp"),
            )

    @staticmethod
    def _add_tool(
        handler: ToolHandler, name: str, now: float | None, target: float | None
    ) -> None:
        """Add a temperature reading to ``handler`` when a value is present."""
        if now is None:
            return
        handler.add(temperatures(name, now, target if target is not None else 0))
