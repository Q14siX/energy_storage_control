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

- [`Tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

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
  Selected favourable block start time. The attributes `favorable_from` and `favorable_until` still describe that selected block. The `data` attribute now contains all favourable 15-minute slots of the selected day, and `all_favorable_blocks` lists every favourable block of that same day.
- `sensor.esc_<primary_home>_state_of_charge`
- `sensor.esc_<primary_home>_grid_power_balance`
- `sensor.esc_<primary_home>_charge_discharge_power`

Additional attributes of this sensor:

- `planned_charge_start`: timestamp when charging is expected to actually begin based on the current evaluation state.
- `planned_charge_start_power`: planned charging power in watts at that start moment.
- If the planned start falls inside the currently active favourable slot, the timestamp refers to the current moment, because ESC can only begin or adjust charging from **now** onward.
- When SoC hysteresis currently blocks charging, or when no charging start is planned, these values are `null`.

### Binary sensor

- `binary_sensor.esc_<home>_favourable_now`

### Number entities

- `number.esc_<home>_favourable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Additional attributes:

- `number.esc_<home>_favourable_threshold` also exposes `current_threshold_price`. This is the current day's exact electricity price threshold up to which ESC considers power favourable.
- Price attributes are intentionally not reduced to two decimal places so the calculation can be traced directly in Home Assistant.

### Switch

- `switch.esc_<primary_home>_command_target_update`

Note: the actual Home Assistant translation keys remain defined by the integration code; the entity ID suffixes themselves do not change.

## Detailed control logic

### Price logic

ESC requests Tibber prices for **today and tomorrow** and keeps the price attributes at calculation precision instead of reducing them to two decimal places.

The `current_threshold_price` attribute of `number.esc_<home>_favourable_threshold` exposes the exact current-day price up to which ESC classifies electricity as favourable.

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

The sensor state still points to one selected favourable block, while `data` and `all_favorable_blocks` expose the full favourable-day view for traceability.

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

Charging only occurs when the **current slot** is within the favourable price range, meaning `price <= threshold_price`.

ESC first calculates the missing energy up to max SoC. It then plans across **all remaining favourable 15-minute slots of the relevant planning day**. Today is used whenever favourable slots are still available today; tomorrow is only used as a fallback.

For each favourable slot, ESC derives a linear price factor between the daily minimum and the daily threshold:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

That means:

- `min_price` → 100 % of available charging power
- `threshold_price` → 0 % charging power
- prices above the threshold are excluded from charging

ESC then allocates the required input energy greedily across the favourable slots:

- cheapest slots first
- later slots win when prices are equal
- the current slot only receives energy if the cheaper remaining slots alone cannot satisfy the target, or if the current slot itself belongs to the cheapest slots still required

The allocation for the current slot becomes `charge_power`. This keeps charging inside the favourable range while preserving headroom for later and cheaper slots.

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
- Charging remains `0`: current slot not favourable, later cheaper favourable slots already cover demand, SoC already at maximum, hysteresis hold, or input limit `0`
- Discharging remains `0`: grid balance too low, SoC at minimum, or output limit `0`
