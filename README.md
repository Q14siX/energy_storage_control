[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5?style=flat&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat&logo=hacs&logoColor=white)](https://hacs.xyz/)
[![Version](https://img.shields.io/github/v/release/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Version)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-41BDF5?style=flat)](#)
[![Stars](https://img.shields.io/github/stars/Q14siX/energy_storage_control?style=flat&logo=github&color=41BDF5&label=Stars)](https://github.com/Q14siX/energy_storage_control/stargazers)
[![Languages](https://img.shields.io/badge/Languages-DE%20%7C%20EN%20%7C%20DA%20%7C%20NL%20%7C%20NO%20%7C%20SV-41BDF5?style=flat&logo=translate&logoColor=white)](#)
[![License](https://img.shields.io/github/license/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=License)](https://github.com/Q14siX/energy_storage_control/blob/main/LICENSE)
[![Downloads](https://img.shields.io/github/downloads/Q14siX/energy_storage_control/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Issues](https://img.shields.io/github/issues/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Issues)](https://github.com/Q14siX/energy_storage_control/issues)

<p align="center"><img src="https://raw.githubusercontent.com/Q14siX/energy_storage_control/main/brand/logo.png" alt="Energy Storage Control logo"></p>

# Energy Storage Control

Detailed documentation is available in the language-specific files below.

- 🇩🇪 [Deutsch](README/README_de.md)
- 🇺🇸 [English](README/README_en.md)
- 🇬🇧 [English (UK)](README/README_en-GB.md)
- 🇩🇰 [Dansk](README/README_da.md)
- 🇳🇱 [Nederlands](README/README_nl.md)
- 🇳🇴 [Norsk Bokmål](README/README_nb.md)
- 🇳🇴 [Norsk](README/README_no.md)
- 🇸🇪 [Svenska](README/README_sv.md)

## What this repository contains

Energy Storage Control is a Home Assistant custom integration that combines Tibber price data, grid power measurements, SoC limits, technical charge/discharge limits, and optional external command targets to derive a signed charge/discharge command for a storage system.

The detailed language files document the current charging model, including the charge/discharge power sensor attributes `planned_charge_start` and `planned_charge_start_power`, the `current_threshold_price` attribute of the favorable-threshold entity, and the slot-based favorable charging logic. The favorable-phase sensor now keeps its selected block state while exposing all favorable slots of the selected day in `data` and all favorable day blocks in `all_favorable_blocks`. Price attributes are intentionally exposed without reducing them to two decimal places so the calculation remains traceable.

The repository is prepared for GitHub and HACS custom repository usage:

- `custom_components/energy_storage_control/` contains the actual integration.
- `brand/` contains repository brand assets for GitHub/HACS presentation.
- `custom_components/energy_storage_control/brand/` contains local brand assets for Home Assistant.
- `hacs.json` enables HACS custom repository handling.
- `.github/workflows/validate.yml` runs HACS validation.
- `.github/workflows/hassfest.yml` runs hassfest validation.
- `README/README_*.md` contains the detailed language-specific documentation.

## Quick installation

### HACS
1. Open HACS.
2. Add `https://github.com/Q14siX/energy_storage_control` as a custom repository of type **Integration**.
3. Install **Energy Storage Control**.
4. Restart Home Assistant.
5. Add the integration in **Settings → Devices & Services**.

### Manual
Copy `custom_components/energy_storage_control` into your Home Assistant configuration directory under `custom_components/`.

## Important runtime requirements

The integration requires the following Home Assistant integrations to be configured before setup:

- [`Tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

## Note

The README files use a GitHub RAW image URL for the logo. This works as intended once the repository is pushed to GitHub and the default branch is `main`.
