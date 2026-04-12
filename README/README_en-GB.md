[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5?style=flat&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat&logo=hacs&logoColor=white)](https://hacs.xyz/)
[![Version](https://img.shields.io/github/v/release/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Version)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Maintained](https://img.shields.io/badge/Maintained%3F-yes-41BDF5?style=flat)](#)
[![Stars](https://img.shields.io/github/stars/Q14siX/energy_storage_control?style=flat&logo=github&color=41BDF5&label=Stars)](https://github.com/Q14siX/energy_storage_control/stargazers)
[![Languages](https://img.shields.io/badge/Languages-DE%20%7C%20EN-41BDF5?style=flat&logo=translate&logoColor=white)](#)
[![License](https://img.shields.io/github/license/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=License)](https://github.com/Q14siX/energy_storage_control/blob/main/LICENSE)
[![Downloads](https://img.shields.io/github/downloads/Q14siX/energy_storage_control/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/Q14siX/energy_storage_control/releases/latest)
[![Issues](https://img.shields.io/github/issues/Q14siX/energy_storage_control?style=flat&color=41BDF5&label=Issues)](https://github.com/Q14siX/energy_storage_control/issues)

<p align="center"><img src="https://raw.githubusercontent.com/Q14siX/energy_storage_control/main/brand/logo.png" alt="Energy Storage Control logo" width="220"></p>

# Energy Storage Control

[← Back to language overview](../README.md)

## Overview

This file mirrors the English documentation, using UK English wording where practical.

**Energy Storage Control** is a Home Assistant custom integration for price-aware control of an energy storage system. It combines Tibber price windows, grid power readings, SoC limits, technical charge/discharge limits, and an optional writable target entity to derive a **signed power command**.

Sign convention:

- **negative** = charging
- **positive** = discharging

## Key points

- current Tibber prices per Tibber home
- favourable phase detection
- binary indication of whether the current slot is favourable
- live grid power balance calculation
- merged minimum, maximum, and current SoC handling
- configurable threshold, fixed base grid load, and battery capacity
- additional user charge/discharge limits
- optional synchronisation to an external helper entity
- persistent cache, daily statistics, and learned charge efficiency

## Requirements

The following integrations must already be configured:

- `tibber`
- `zendure_ha`

You also need suitable entities for:

- grid import
- optional grid export
- minimum, maximum, and current SoC
- technical output and input limits
- actual charging power into the battery
- optionally a writable `number` or `input_number` as command target

## Defaults

- favourable threshold: **20 %**
- fixed base grid power: **0 W**
- battery capacity: **2.44 kWh**
- SoC hysteresis: **2 %**
- default planning charge efficiency: **90 %**

## Repository structure

```text
energy_storage_control/
├── .github/
│   └── workflows/
│       ├── hassfest.yml
│       └── validate.yml
├── brand/
│   ├── icon.png
│   └── logo.png
├── custom_components/
│   └── energy_storage_control/
│       ├── __init__.py
│       ├── binary_sensor.py
│       ├── brand/
│       │   ├── icon.png
│       │   └── logo.png
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── entity.py
│       ├── manifest.json
│       ├── number.py
│       ├── power.py
│       ├── sensor.py
│       ├── switch.py
│       └── translations/
├── README/
│   └── README_*.md
├── .gitignore
├── GITHUB_PUBLISHING_CHECKLIST.md
├── hacs.json
└── README.md
```

## Installation

Add `https://github.com/Q14siX/energy_storage_control` to HACS as a **Custom repository** of type **Integration**, install it, restart Home Assistant, and then add the integration in **Settings → Devices & Services**.

For a manual installation, copy `custom_components/energy_storage_control` into `custom_components/` inside your Home Assistant configuration directory.

## Configuration flow

The flow covers price settings, grid sources, SoC sources, charge feedback, battery settings, technical limits, user limits, and an optional command target.

Validation rules include:

- at least one import source is required
- import and export may not use the same entity
- min/max/current SoC must be three different entities
- technical input and output may not use the same entity
- the command target must accept both negative and positive values

## Entities

### Sensors

- `sensor.esc_<home>_current_price`
- `sensor.esc_<home>_favourable_phase`
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

### Binary sensor

- `binary_sensor.esc_<home>_favourable_now`

### Number entities

- `number.esc_<home>_favourable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

### Switch

- `switch.esc_<primary_home>_command_target_update`

Note: the actual Home Assistant translation keys remain defined by the integration code; the entity ID suffixes themselves do not change.

## Detailed control logic

### Price logic

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

A price is favourable when:

```text
price <= threshold_price
```

### Favourable phase selection

Priority order:

1. current favourable block today
2. next future favourable block today
3. first favourable block tomorrow
4. otherwise the most recent favourable block today if tomorrow is unavailable

### Grid balance

```text
grid_power_balance = import_watts - export_watts
```

When multiple sources are configured, ESC uses the **most recently updated** valid source.

### Discharging

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

No discharge happens when SoC is at or below minimum. The value is also clamped by the user limit and the technical output limit.

### Charging

Charging only occurs during an active favourable phase. ESC calculates the missing energy up to max SoC and allocates that demand across the remaining slots of the current favourable phase, prioritising the cheapest slots.

### Hysteresis

When SoC reaches the configured maximum, a hold remains active until SoC falls below `max_soc - hysteresis`.

### Signed command

```text
if current phase is favourable:
    command = -charge_power
else:
    command = discharge_power
```

### Learned charge efficiency

Learning only occurs during genuine positive charging. A session is only accepted if the requested energy, stored energy, duration, and calculated efficiency all fall inside the configured acceptance window.

## Persistence and runtime

Price data, daily grid statistics, and learned efficiency values are stored in the Home Assistant store. Prices refresh every quarter hour. Daily grid statistics reset at midnight.

## Multi-home

Price-related entities are created per Tibber home. Global entities are tied to the **first** detected home.

## Troubleshooting

- No power sources: verify numeric values and power units
- No SoC sources: verify `%`, `device_class: battery`, or a `0..100` range
- Target does not update: check the switch, the signed range, and that the target is not also used as a limit source
- Charging remains `0`: no favourable phase, SoC already at maximum, hysteresis hold, or input limit `0`
- Discharging remains `0`: grid balance too low, SoC at minimum, or output limit `0`
