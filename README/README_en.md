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

**Energy Storage Control** is a Home Assistant custom integration for price-aware control of an energy storage system. It combines Tibber price windows, grid power measurements, SoC limits, technical charge/discharge limits, and optional writable target entities to derive a **signed power command**.

The logic is intentionally separated into clear functional layers:

- **price logic** decides whether a time slot is favorable
- **discharge logic** reacts to real grid demand
- **charge logic** distributes missing energy across all remaining favorable slots of the relevant planning day
- **SoC logic** protects lower and upper boundaries
- **hysteresis** prevents oscillation near the upper SoC limit
- **learning logic** derives the real charge efficiency from actual charging sessions
- **command target synchronization** can optionally write the signed command to an external `number` or `input_number`

In this integration the command sign is:

- **negative** = charging
- **positive** = discharging

## Feature set

This integration provides much more than one single control value:

- current Tibber prices per Tibber home
- detection of favorable price phases
- a boolean indicator showing whether the current slot is favorable
- live grid power balance calculation
- merged minimum, maximum, and current SoC handling
- configurable thresholds, base grid power, and battery capacity
- additional user-defined charge and discharge limits
- optional synchronization of the signed command into an external helper entity
- persistent cache, daily grid statistics, and learned efficiency values

## Requirements

Before setup, the following Home Assistant integrations must already be configured:

- [`tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)

Energy Storage Control also expects suitable source entities:

- at least **one grid import power** source
- optionally **one or more grid export power** sources
- one separate entity each for minimum, maximum, and current SoC
- one entity each for technical discharge and charge power limits
- optionally one entity for the **actual battery charge power**
- optionally a writable `number` or `input_number` entity as command target

Supported power sources may be `sensor` or `number` entities with power units such as `mW`, `W`, `kW`, `MW`, `GW`, or `TW`. Entities with `device_class: power` are also accepted.

Supported SoC sources may be:

- `sensor` or `number`
- `device_class: battery`
- percentage-based entities using `%`
- numeric entities that clearly expose a `0..100` range

## Default values

The integration currently uses these defaults:

- favorable threshold: **20 %**
- fixed base grid power: **0 W**
- battery capacity: **2.44 kWh**
- SoC hysteresis: **2 %**
- default planning charge efficiency: **90 %**
- user output limit: **0 W** up to the current technical maximum
- user input limit: **0 W** up to the current technical maximum

## Installation

### Install via HACS

1. Open HACS.
2. Open **Custom repositories**.
3. Add `https://github.com/Q14siX/energy_storage_control`.
4. Select type **Integration**.
5. Install **Energy Storage Control**.
6. Restart Home Assistant.
7. Add the integration under **Settings → Devices & Services**.

### Manual installation

1. Copy `custom_components/energy_storage_control` from this repository.
2. Place it in your Home Assistant configuration directory under `custom_components/`.
3. Restart Home Assistant.
4. Add the integration through the UI.

## Configuration flow in detail

The configuration flow is step-based and validates every selection.

### 1. Price settings
This step collects two core values:

- **Favorable threshold**: percentage used to determine favorable prices
- **Base grid power**: fixed grid base load in watts

### 2. Grid sources
This step selects the power sources for grid import and optional grid export.

Important behavior:

- at least **one import source** is required
- export is optional
- multiple sources are allowed
- ESC uses the **most recently updated** valid source
- the same entity cannot be used for both import and export

### 3. SoC sources
Three different entities must be selected:

- minimum SoC
- maximum SoC
- current SoC

All three must be different. The integration explicitly validates whether the selected entities are suitable as SoC sources.

### 4. Charge feedback source
This entity reports the **actual charging power into the battery**. It is not only used for display purposes, but also for learning the real charge efficiency.

### 5. Battery settings
This step sets:

- usable battery capacity in `kWh`
- SoC hysteresis in `%`

### 6. Technical power limits
This step selects the external source entities for the technical limits:

- **Output limit** = technical discharge limit
- **Input limit** = technical charge limit

The same entity cannot be reused for both.

### 7. User limits
In addition to the technical limits, the user can define:

- user discharge limit
- user charge limit

These values are always clamped to the currently active technical source values.

### 8. Command target
Optionally, a writable `number` or `input_number` entity can be selected.

That target entity must:

- be writable
- allow positive **and** negative values
- not be an ESC-owned internal entity
- not be used as a technical power limit source

## Created entities

The integration creates Home Assistant entities with a stable `esc_` prefix.

### Sensors

- `sensor.esc_<home>_current_price`  
  Current Tibber price in `€/kWh`. Attributes include min/avg/max values for today, tomorrow, and overall, plus raw price rows.

- `sensor.esc_<home>_favorable_phase`  
  Start timestamp of the currently relevant favorable phase. Attributes include start, end, threshold values, and min/avg/max values for that selected block. The `data` attribute contains all favorable 15-minute slots of the selected day, and `all_favorable_blocks` lists every favorable block of that same day.

- `sensor.esc_<primary_home>_state_of_charge`  
  Combined current SoC. Attributes include minimum and maximum SoC.

- `sensor.esc_<primary_home>_grid_power_balance`  
  Signed grid balance in watts. Attributes include import, optional export, and current-day min/max/avg values.

- `sensor.esc_<primary_home>_charge_discharge_power`  
  Signed command value. Attributes include `charge_power`, `discharge_power`, learned efficiency values, sample count, command target information, plus the planning attributes below.

Additional attributes of this sensor:

- `planned_charge_start`: timestamp when charging is expected to actually begin based on the current evaluation state.
- `planned_charge_start_power`: planned charging power in watts at that start moment.
- If the planned start falls inside the currently active favourable slot, the timestamp refers to the current moment, because ESC can only begin or adjust charging from **now** onward.
- When SoC hysteresis currently blocks charging, or when no charging start is planned, these values are `null`.

### Binary sensor

- `binary_sensor.esc_<home>_favorable_now`  
  `on` when the current time falls inside the currently relevant favorable phase.

### Number entities

- `number.esc_<home>_favorable_threshold`
- `number.esc_<primary_home>_base_grid_power`
- `number.esc_<primary_home>_battery_capacity`
- `number.esc_<home>_soc_hysteresis`
- `number.esc_<primary_home>_user_output_power_limit`
- `number.esc_<primary_home>_user_input_power_limit`

Additional attributes:

- `number.esc_<home>_favorable_threshold` also exposes `current_threshold_price`. This is the current day's exact electricity price threshold up to which ESC considers power favorable.
- Price attributes are intentionally not reduced to two decimal places so the calculation can be traced directly in Home Assistant.
- battery capacity also exposes current energy plus energy at minimum and maximum SoC
- user limit entities show the currently effective technical source value

### Switch

- `switch.esc_<primary_home>_command_target_update`

When this switch is enabled, ESC writes the calculated signed command to the configured target entity. When disabled, ESC intentionally writes `0`.

## Control logic in detail

### Price logic and favorable threshold

The integration requests Tibber prices for **today and tomorrow** using the Home Assistant service `tibber.get_prices`. All rows are normalized to local time. Price attributes are intentionally not reduced to two decimal places so the calculation can be traced directly in Home Assistant.

The `current_threshold_price` attribute of `number.esc_<home>_favorable_threshold` exposes the exact current-day price up to which ESC classifies electricity as favorable.

The daily favorable threshold is calculated as:

```text
threshold_price = min_price + ((max_price - min_price) * threshold_percent / 100)
```

A price is considered favorable when:

```text
price <= threshold_price
```

### Relevant favorable phase selection

ESC builds contiguous favorable blocks per day. The selected block follows this exact priority order:

1. the current favorable block from today
2. the next future favorable block from today
3. the first favorable block from tomorrow
4. if tomorrow is still unavailable, the most recent favorable block from today

This means the integration always prioritizes **today** and only falls back to **tomorrow** when necessary. The sensor state still points to one selected favorable block, while the attributes `data` and `all_favorable_blocks` expose the full favorable-day view used for traceability.

### Grid power balance

The signed grid balance is calculated as:

```text
grid_power_balance = import_watts - export_watts
```

If no export source is configured, the balance is simply the import value.

When multiple import or export sensors are configured, ESC uses the **most recently updated** valid entity on each side.

### Discharge logic

Discharging intentionally follows the documented ESC rule directly:

```text
discharge_power = max(grid_power_balance - base_grid_power, 0)
```

Additional protection rules:

- if `current_soc <= min_soc`, discharge is forced to `0`
- discharge is clamped to the configured user output limit
- the user output limit itself is clamped to the current technical output limit

### Charge logic

Charging only happens when the **current slot** is inside the favorable price range, meaning `price <= threshold_price`.

Basic prerequisites:

- current SoC available
- maximum SoC available
- battery capacity > 0
- user input limit > 0
- charge efficiency > 0

ESC first calculates how much energy is still missing up to the target SoC:

```text
missing_soc_percent = max_soc - current_soc
required_stored_energy_kwh = battery_capacity_kwh * missing_soc_percent / 100
required_input_energy_kwh = required_stored_energy_kwh / (charge_efficiency_percent / 100)
```

ESC then builds the charge plan from **all remaining favorable 15-minute slots of the relevant planning day**. As long as favorable slots are still available today, ESC plans against today; only otherwise does it fall back to tomorrow.

For each favorable slot, ESC first derives a price-based charge factor:

```text
price_factor = (threshold_price - slot_price) / (threshold_price - min_price)
```

This means:

- `min_price` → 100 % of the available charge power
- `threshold_price` → 0 % charge power
- prices above the threshold are excluded from charging

ESC then allocates the required input energy **greedily** across those favorable slots:

- cheapest slots first
- if prices are equal, later slots are preferred
- the current slot only receives energy when the cheaper remaining slots alone are not sufficient, or when the current slot itself belongs to the cheapest slots still needed to reach the target

The energy assigned to the current slot becomes the `charge_power` value.

This keeps charging strictly inside the favorable range while still giving later and cheaper slots priority over earlier slots that are merely acceptable.

### SoC hysteresis

Hysteresis prevents rapid on/off switching near the upper SoC boundary.

Logic:

- once `current_soc >= max_soc`, a charge hold is activated for the **current favorable phase**
- that hold stays active until `current_soc <= max_soc - hysteresis`
- the hold only applies inside the same favorable phase
- when a new favorable phase starts, the logic is evaluated again

### Signed command value

The final command is:

- **negative** while charging
- **positive** while discharging

Formally:

```text
if current phase is favorable:
    command = -charge_power
else:
    command = discharge_power
```

### Charge-efficiency learning

The integration can learn its planning efficiency from real charging sessions. It uses the configured entity that reports the actual charging power into the battery.

A learning session only runs while real positive charging power is measured. On session finalization, ESC only accepts the result when all of these conditions are met:

- requested energy at least **0.05 kWh**
- stored energy at least **0.01 kWh**
- duration at least **300 seconds**
- calculated efficiency between **70 %** and **100 %**

Then:

```text
efficiency_percent = stored_energy / requested_energy * 100
```

The overall learned efficiency is stored as a running average over all accepted samples.

### Command target synchronization

If a command target is configured, ESC can write the signed command using `number.set_value` or `input_number.set_value`.

Safety rules:

- no ESC-owned internal entities as target
- no target that is also used as an input/output limit source
- target must accept both negative and positive values
- value is clamped to the target entity min/max range before writing

When target updates are disabled, ESC writes `0`.

## Persistence and runtime behavior

The integration stores, via the Home Assistant store:

- price cache per Tibber home
- daily grid power statistics
- learned efficiency values and power-command state

On startup, volatile live regulation values are intentionally reset so that outdated command values are never restored from cache.

Scheduled behavior:

- price refresh every quarter hour
- daily grid statistics reset at midnight
- state listeners for grid power, SoC, charge feedback, and power limit sources
- debounced saving of grid statistics

## Multi-home behavior

The integration supports multiple Tibber homes on the price side. This affects the home-specific entities:

- current price
- favorable phase
- favorable now
- favorable threshold

However, global entities such as grid balance, SoC, charge/discharge power, and user power limits are bound to the **first detected Tibber home**.

That detail matters when one Tibber account contains multiple homes.

## Troubleshooting

### No power sources are offered
Check whether the entities are numeric and expose a valid power unit or `device_class: power`.

### No SoC sources are offered
Check whether the entity exposes `%`, `device_class: battery`, or a sensible `0..100` range.

### The command is not written to the target entity
Check:

- command target configured?
- `command_target_update` switch enabled?
- target allows both negative **and** positive values?
- target is not also used as an input/output limit source?

### Charging stays at 0 W
Typical reasons:

- the current slot is outside the favorable price range
- later cheaper favorable slots already cover the remaining energy demand
- current SoC is already at maximum
- hysteresis hold is still active
- user input limit = 0
- technical input limit = 0
- no valid SoC/capacity/feedback basis available

### Discharging stays at 0 W
Typical reasons:

- grid balance is below or equal to the base grid power
- current SoC is at minimum
- user output limit = 0
- technical output limit = 0

## Support

- Repository owner: **Q14siX**
- Repository: **energy_storage_control**

Once published, bug reports and improvements should be managed directly in the GitHub repository.
