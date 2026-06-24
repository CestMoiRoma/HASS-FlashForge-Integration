# Status reference

This page documents every value the **Status** and **Print Status** sensors can
report, so you can use them reliably in automations and dashboards.
(Resolves [#103](https://github.com/joseffallman/hass_flashforge/issues/103).)

See also: [Automation examples](AUTOMATIONS.md).

The values depend on which protocol your printer speaks:

- **Legacy printers** (Adventurer 3 / 4, Guider, Creator Pro …) use the M-code
  protocol on port `8899`. Values come straight from the printer's `M119` /
  `M27` responses.
- **Newer printers** (Adventurer 5M / 5M Pro, AD5X, Creator series) use the HTTP
  API on port `8898`. The raw value comes from the `/detail` response's
  `status` field.

---

## `status` sensor — Machine status

The main `Status` sensor reports the overall machine state.

### Legacy printers (`MachineStatus` from `M119`)

| Value                 | Meaning                                              |
| --------------------- | ---------------------------------------------------- |
| `READY`               | Idle and ready to start a job.                       |
| `BUILDING_FROM_SD`    | Printing a job (from internal storage / SD).         |
| `BUILDING_COMPLETED`  | The job finished.                                    |
| `PAUSED`              | The current job is paused.                           |

### Newer printers (raw `status`, normalised to the names below)

The integration maps the new API's lower-case status to the same legacy-style
names where possible. The **Print Status** sensor (below) keeps the raw value.

| Normalised value      | Raw API value     | Meaning                                |
| --------------------- | ----------------- | -------------------------------------- |
| `READY`               | `ready`           | Idle and ready.                        |
| `BUSY`                | `busy`            | Busy with a non-print task.            |
| `HEATING`             | `heating`         | Heating up before a print.             |
| `CALIBRATING`         | `calibrate_doing` | Running bed leveling / calibration.    |
| `BUILDING_FROM_SD`    | `printing`        | Printing.                              |
| `PAUSING`             | `pausing`         | Transitioning to paused.               |
| `PAUSED`              | `paused`          | Paused.                                |
| `BUILDING_COMPLETED`  | `completed`       | Print finished.                        |
| `CANCELING`           | `canceling`       | Cancelling the current job.            |
| `CANCELLED`           | `cancel`          | The job was cancelled.                 |
| `ERROR`               | `error`           | The printer reported an error.         |

---

## `print_status` sensor — Print status

### Legacy printers

The `Print Status` sensor exposes the raw `Status:` line from the `M119`
response, formatted as four flags:

```
Status: S:1 L:0 J:0 F:0
```

| Flag | Name       | Meaning                                                  |
| ---- | ---------- | -------------------------------------------------------- |
| `S`  | Status     | Endstop / overall sub-status (`1` = ready, varies).      |
| `L`  | Led        | `1` while LED-related activity is in progress.           |
| `J`  | Job        | `1` while a job is active.                                |
| `F`  | File       | `1` while a file is selected / open.                     |

> These flags are firmware-defined and not officially documented by FlashForge;
> the meanings above are the community's best understanding. Treat them as
> advisory.

### Newer printers

For new-API printers, `Print Status` holds the **raw** `status` string from the
`/detail` response (`ready`, `printing`, `paused`, `completed`, `busy`,
`heating`, `calibrate_doing`, `pausing`, `canceling`, `cancel`, `error`).

---

## `move_mode` sensor

| Value    | Meaning                                  |
| -------- | ---------------------------------------- |
| `READY`  | The toolhead is idle.                    |
| `MOVING` | The toolhead is moving (printing/homing).|

On legacy printers this comes from the `MoveMode` field of `M119`. On newer
printers it is derived from `status` (`MOVING` while printing/busy/heating,
otherwise `READY`).
