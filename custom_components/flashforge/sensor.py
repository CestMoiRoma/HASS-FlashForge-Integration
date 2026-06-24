"""Add Flashforge sensors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_NAME, DOMAIN
from .new_api import NewApiPrinter

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from ffpp.Printer import Printer
    from ffpp.Printer import temperatures as Tool  # noqa: N812
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data_update_coordinator import FlashForgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _finish_time(printer: Printer) -> datetime | None:
    """Return the estimated wall-clock finish time of the current job."""
    seconds = getattr(printer, "estimated_time", None)
    if not seconds:
        return None
    return dt_util.utcnow() + timedelta(seconds=seconds)


@dataclass(frozen=True)
class FlashforgeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description with added value fnc."""

    value_fnc: Callable[[Printer], str | int | float | datetime | None] | None = None


@dataclass(frozen=True)
class FlashforgeTempSensorEntityDescription(FlashforgeSensorEntityDescription):
    """Sensor entity description for temperature sensors."""

    value_fnc: Callable[[Tool], float] | None = None


SENSORS: tuple[FlashforgeSensorEntityDescription, ...] = (
    FlashforgeSensorEntityDescription(
        key="status",
        icon="mdi:printer-3d",
        value_fnc=lambda printer: printer.machine_status,
    ),
    FlashforgeSensorEntityDescription(
        key="job_percentage",
        icon="mdi:file-percent",
        native_unit_of_measurement=PERCENTAGE,
        value_fnc=lambda printer: printer.print_percent,
    ),
    FlashforgeSensorEntityDescription(
        key="file",
        icon="mdi:file-cad",
        value_fnc=lambda printer: printer.job_file,
    ),
    FlashforgeSensorEntityDescription(
        key="layers",
        icon="mdi:layers-triple",
        value_fnc=lambda printer: printer.job_layers,
    ),
    FlashforgeSensorEntityDescription(
        key="print_layer",
        icon="mdi:layers-edit",
        value_fnc=lambda printer: printer.print_layer,
    ),
    FlashforgeSensorEntityDescription(
        key="print_status",
        icon="mdi:printer-3d",
        value_fnc=lambda printer: printer.status,
    ),
    FlashforgeSensorEntityDescription(
        key="move_mode",
        icon="mdi:move-resize",
        value_fnc=lambda printer: printer.move_mode,
    ),
)
# Sensors only available through the newer HTTP API (port 8898).
NEW_API_SENSORS: tuple[FlashforgeSensorEntityDescription, ...] = (
    FlashforgeSensorEntityDescription(
        key="time_remaining",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fnc=lambda printer: printer.estimated_time,
    ),
    FlashforgeSensorEntityDescription(
        key="finish_time",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fnc=_finish_time,
    ),
    FlashforgeSensorEntityDescription(
        key="elapsed_time",
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fnc=lambda printer: printer.print_duration,
    ),
    FlashforgeSensorEntityDescription(
        key="chamber_current",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fnc=lambda printer: printer.chamber_temp,
    ),
    FlashforgeSensorEntityDescription(
        key="chamber_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fnc=lambda printer: printer.chamber_target,
    ),
    FlashforgeSensorEntityDescription(
        key="speed_adjust",
        icon="mdi:speedometer",
        native_unit_of_measurement=PERCENTAGE,
        value_fnc=lambda printer: printer.print_speed_adjust,
    ),
    FlashforgeSensorEntityDescription(
        key="nozzle_size",
        icon="mdi:printer-3d-nozzle",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fnc=lambda printer: printer.nozzle_size,
    ),
    FlashforgeSensorEntityDescription(
        key="filament_type",
        icon="mdi:printer-3d-nozzle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fnc=lambda printer: printer.filament_type,
    ),
    FlashforgeSensorEntityDescription(
        key="error_code",
        icon="mdi:alert-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fnc=lambda printer: printer.error_code,
    ),
    FlashforgeSensorEntityDescription(
        key="free_disk_space",
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fnc=lambda printer: printer.free_disk_space,
    ),
    FlashforgeSensorEntityDescription(
        key="total_filament",
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fnc=lambda printer: printer.cumulative_filament,
    ),
    FlashforgeSensorEntityDescription(
        key="total_print_time",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fnc=lambda printer: printer.cumulative_print_time,
    ),
)
TEMP_SENSORS: tuple[FlashforgeSensorEntityDescription, ...] = (
    FlashforgeTempSensorEntityDescription(
        key="_current",
        value_fnc=lambda tool: tool.now,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FlashforgeTempSensorEntityDescription(
        key="_target",
        value_fnc=lambda tool: tool.target,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available FlashForge sensors platform."""
    _LOGGER.debug("async_setup_entry- sensors")
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[SensorEntity] = []

    if coordinator.printer.connected:
        # Loop all extruders and add current and target temp sensors.
        for i, tool in enumerate(coordinator.printer.extruder_tools):
            name = (
                f"extruder{i}"
                if len(coordinator.printer.extruder_tools) > 1
                else "extruder"
            )
            for description in TEMP_SENSORS:
                sensor = FlashForgeTempSensor(
                    coordinator=coordinator,
                    description=description,
                    name=name,
                    tool_name=tool.name,
                )
                entities.append(sensor)

        # Loop all beds and add current and target temp sensors.
        for i, tool in enumerate(coordinator.printer.bed_tools):
            name = f"bed{i}" if len(coordinator.printer.bed_tools) > 1 else "bed"
            for description in TEMP_SENSORS:
                sensor = FlashForgeTempSensor(
                    coordinator=coordinator,
                    description=description,
                    name=name,
                    tool_name=tool.name,
                )
                entities.append(sensor)

    for description in SENSORS:
        _LOGGER.debug(f"setup {description}")  # noqa: G004
        entities.append(
            FlashForgeSensor(
                coordinator=coordinator,
                description=description,
            )
        )

    # Extra telemetry is only available through the newer HTTP API.
    if isinstance(coordinator.printer, NewApiPrinter):
        entities.extend(
            FlashForgeSensor(coordinator=coordinator, description=description)
            for description in NEW_API_SENSORS
        )

    async_add_entities(entities)


class FlashForgeSensor(CoordinatorEntity, SensorEntity):
    """Representation of an FlashForge sensor."""

    coordinator: FlashForgeDataUpdateCoordinator
    entity_description: FlashforgeSensorEntityDescription

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        description: FlashforgeSensorEntityDescription,
        name: str = "",
        tool_name: str | None = None,
    ) -> None:
        """Initialize a new Flashforge sensor."""
        super().__init__(coordinator)
        self._device_id = coordinator.config_entry.unique_id
        self._attr_device_info = coordinator.device_info
        self.entity_description = description
        # Fall back to a sensible prefix so entity ids never become "none_..."
        # when the printer reports no name/serial (see issue #108).
        title = coordinator.config_entry.title or DEFAULT_NAME
        unique_prefix = coordinator.config_entry.unique_id or DEFAULT_NAME
        self._attr_name = (
            f"{title} {name.title()}{description.key.replace('_', ' ').title()}"
        )
        self._attr_unique_id = f"{unique_prefix}_{name}{description.key}"

        self.tool_name = tool_name

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return sensor state."""
        if self.entity_description.value_fnc is None:
            return None

        if isinstance(self.entity_description, FlashforgeSensorEntityDescription):
            # If it's a normal sensor we can just pass the printer
            return self.entity_description.value_fnc(self.coordinator.printer)
        return None


class FlashForgeTempSensor(FlashForgeSensor):
    """Representation of an FlashForge temperature sensor."""

    entity_description: FlashforgeTempSensorEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return sensor state."""
        if self.entity_description.value_fnc is None:
            return None
        if self.tool_name:
            # If toolname is set we need to get that tool and pass it to the lambda.
            tool = self.coordinator.printer.extruder_tools.get(self.tool_name)
            if tool is None:
                tool = self.coordinator.printer.bed_tools.get(self.tool_name)
            if tool is not None:
                return self.entity_description.value_fnc(tool)

        return None
