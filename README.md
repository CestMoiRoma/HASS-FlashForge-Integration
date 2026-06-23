# FlashForge 3D Printer — Home Assistant integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]

_Monitor and control your [FlashForge][flashforge] 3D printer locally from Home Assistant._

This integration polls your printer over its **local network** (no cloud
account required) and exposes its state and controls as Home Assistant
entities.

---

## Supported printers

FlashForge printers use two different local protocols, and this integration
supports both:

| Connection | Port | Models (non-exhaustive) | Setup |
| ---------- | ---- | ----------------------- | ----- |
| **Legacy** (M-code TCP) | `8899` | Adventurer 3, Adventurer 4, Guider II/III, Creator Pro | IP address only |
| **New API** (HTTP + Check Code) | `8898` | Adventurer 5M / 5M Pro, AD5X, **Creator 5** and other newer models | LAN mode + serial + Check Code |

> Newer printers no longer expose the open `8899` service. They require **LAN
> mode** to be turned on and an **8-digit Check Code**. See
> [Adding a newer printer](#adding-a-newer-printer-creator-5--5m--ad5x) below.
> _(Adds Creator 5 support — resolves upstream [#116](https://github.com/joseffallman/hass_flashforge/issues/116).)_

## Provided entities

| Platform | What you get |
| -------- | ------------ |
| `sensor` | Machine status, print status, job %, current/total layers, current file, move mode, and bed + extruder current/target **temperatures**. |
| `camera` | Live MJPEG feed from the printer's camera (if equipped). |
| `light`  | Chamber LED on/off. |
| `select` | Pick a stored file to print. |
| `button` | Pause, Continue, Abort, and Print-selected-file. |

### Services

`flashforge.pause`, `flashforge.continue_print`, `flashforge.abort`,
`flashforge.print_file` (takes `file_name`), and `flashforge.get_file_names`
(returns the list of files stored on the printer).

📖 **Status / Print Status value reference:** see [docs/STATUS.md](docs/STATUS.md).

---

## Installation

### HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/CestMoiRoma/HASS-FlashForge-Integration` with the
   category **Integration**.
3. Install **FlashForge** and restart Home Assistant.

### Manual

1. Copy the `custom_components/flashforge/` folder from this repository into your
   Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

All setup is done in the UI: **Settings → Devices & Services → Add Integration
→ FlashForge**. You'll be asked to pick the printer type.

### Adding a legacy printer

Choose **Legacy printer**. Either enter the printer's IP address (port defaults
to `8899`), or leave the fields empty to auto-discover a printer on your
network.

### Adding a newer printer (Creator 5 / 5M / AD5X)

1. On the printer's touchscreen, go to **Settings → Network → LAN Mode** and
   enable it. Note the **Check Code** (8 digits) and the **serial number** shown
   there.
2. In Home Assistant, choose **Newer printer** and enter the printer's **IP
   address**, **serial number**, and **Check Code**.

---

## Credits

- **Original integration:** This project is a fork of
  [`joseffallman/hass_flashforge`][upstream] by Josef Fällman. All credit for
  the original design, the legacy protocol support and the `ffpp` library goes
  to the upstream author. 🙏
- **Printers:** [FlashForge][flashforge] — for the 3D printers this integration
  talks to.
- New-API (port 8898) support is informed by the community
  [unofficial FlashForge API documentation](https://github.com/Parallel-7/flashforge-api-docs).

## Contributions are welcome!

If you'd like to contribute, please read the
[Contribution guidelines](CONTRIBUTING.md).

***

[flashforge]: https://www.flashforge.com/
[upstream]: https://github.com/joseffallman/hass_flashforge
[commits-shield]: https://img.shields.io/github/commit-activity/y/CestMoiRoma/HASS-FlashForge-Integration.svg?style=for-the-badge
[commits]: https://github.com/CestMoiRoma/HASS-FlashForge-Integration/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/CestMoiRoma/HASS-FlashForge-Integration.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/CestMoiRoma/HASS-FlashForge-Integration.svg?style=for-the-badge
[releases]: https://github.com/CestMoiRoma/HASS-FlashForge-Integration/releases
