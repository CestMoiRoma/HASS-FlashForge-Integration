"""Tests for the new-API (port 8898) printer adapter.

These tests exercise the field mapping from a ``/detail`` response onto the
ffpp-compatible properties consumed by the rest of the integration. They do not
require Home Assistant or a real printer.
"""

from custom_components.flashforge.new_api import NewApiPrinter

SAMPLE_DETAIL = {
    "status": "printing",
    "printProgress": 0.45,
    "printLayer": 50,
    "targetPrintLayer": 100,
    "platTemp": 58.0,
    "platTargetTemp": 60.0,
    "rightTemp": 209.0,
    "rightTargetTemp": 210.0,
    "leftTemp": 30.0,
    "leftTargetTemp": 0.0,
    "lightStatus": "open",
    "firmwareVersion": "v3.1.3",
    "name": "Creator5",
    "printFileName": "boat.gcode",
    "pid": 38,
    "cameraStreamUrl": "http://192.168.1.20:8080/?action=stream",
}


def _printer() -> NewApiPrinter:
    """Return an adapter whose network layer is bypassed in tests."""
    return NewApiPrinter("192.168.1.20", "SNCR5123", "12345678", session=None)


async def test_update_maps_detail_fields() -> None:
    """A printing /detail response maps onto every ffpp property."""
    printer = _printer()

    async def _fake_detail() -> dict:
        return dict(SAMPLE_DETAIL)

    printer.network.getDetail = _fake_detail
    await printer.update()

    assert printer.status == "printing"
    assert printer.machine_status == "BUILDING_FROM_SD"
    assert printer.move_mode == "MOVING"
    assert printer.print_percent == 45
    assert printer.print_layer == 50
    assert printer.job_layers == 100
    assert printer.led is True
    assert printer.firmware == "v3.1.3"
    assert printer.machine_name == "Creator5"
    assert printer.machine_type == "AD5X"
    assert printer.job_file == "boat.gcode"

    bed = printer.bed_tools.get("bed")
    assert bed is not None
    assert bed.now == 58.0
    assert bed.target == 60.0

    right = printer.extruder_tools.get("right")
    assert right is not None
    assert right.now == 209.0
    left = printer.extruder_tools.get("left")
    assert left is not None
    assert len(printer.extruder_tools) == 2


async def test_update_single_extruder() -> None:
    """A printer without a left tool only registers one extruder."""
    printer = _printer()
    detail = dict(SAMPLE_DETAIL)
    del detail["leftTemp"]

    async def _fake_detail() -> dict:
        return detail

    printer.network.getDetail = _fake_detail
    await printer.update()

    assert len(printer.extruder_tools) == 1
    assert printer.extruder_tools.get("left") is None


async def test_ready_status_maps_to_legacy_name() -> None:
    """A ready printer reports the legacy READY status and idle move mode."""
    printer = _printer()

    async def _fake_detail() -> dict:
        return {"status": "ready", "lightStatus": "close"}

    printer.network.getDetail = _fake_detail
    await printer.update()

    assert printer.machine_status == "READY"
    assert printer.move_mode == "READY"
    assert printer.led is False
