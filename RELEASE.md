<p align="center"><img src="https://raw.githubusercontent.com/Q14siX/energy_storage_control/main/brand/logo.png" alt="Energy Storage Control logo" width="220"></p>

# Release Notes – Energy Storage Control

## Version
`20260413.1700`

## Summary
This release documents the current public state of **Energy Storage Control** for `Q14siX/energy_storage_control`.

The integration combines **Tibber spot prices**, **grid power measurements**, **state-of-charge boundaries**, **technical charge/discharge limits**, and an optional **external signed command target** to derive a signed battery power command.

Sign convention:

- **negative** = charge
- **positive** = discharge

## Functional highlights

### Price-aware operation
- Fetches Tibber prices for **today and tomorrow**.
- Calculates a **daily favorable threshold** from the configured threshold percentage.
- Exposes the current price, the currently relevant favorable phase, and the exact current-day threshold price as entities and attributes.
- The favorable-phase sensor keeps a selected block as its state, but now also exposes all favorable slots of the selected day in `data` and all favorable day blocks in `all_favorable_blocks` for transparent traceability.
- Price attributes are intentionally not reduced to two decimal places so users can verify the calculation directly in Home Assistant.

### Unchanged discharge behaviour
- Uses live grid balance and configured base grid power.
- Prevents discharge below minimum SoC.
- Clamps discharge by user and technical output limits.

### Updated charging model
- Charging is only allowed when the **current slot** is inside the favorable price range.
- ESC evaluates **all remaining favorable 15-minute slots of the relevant planning day**.
- Inside that favorable range, charging power is derived linearly between the daily minimum price and the daily threshold price.
- Required charge energy is then allocated greedily to the cheapest favorable slots first, so later and cheaper slots can take priority over earlier but merely acceptable ones.
- The sensor attributes `planned_charge_start` and `planned_charge_start_power` expose the currently planned charging entry point.

### SoC and efficiency protection
- Keeps dedicated minimum, maximum, and current SoC sources.
- Applies configurable SoC hysteresis near the upper boundary.
- Learns real charge efficiency from valid completed charging sessions.

### External command target support
- Can write the signed ESC command into a writable external `number` or `input_number` entity.
- Includes a switch to enable or disable command-target updates.

## Included entities

### Sensors
- Current electricity price
- Favorable phase start timestamp, including all favorable day slots in `data` and all favorable day blocks in `all_favorable_blocks`
- Combined state of charge
- Signed grid power balance
- Signed charge/discharge command

### Binary sensor
- Favorable phase active now

### Number entities
- Favorable threshold, including the `current_threshold_price` attribute
- Base grid power
- Battery capacity
- SoC hysteresis
- User output power limit
- User input power limit

### Switch
- Command target update enable/disable

## Runtime expectations
Before setup, the following Home Assistant integrations must already be available:

- [`Tibber`](https://www.home-assistant.io/integrations/tibber)
- [Zendure Home Assistant Integration](https://github.com/Zendure/Zendure-HA)
The setup flow expects suitable source entities for grid import, optional grid export, minimum/maximum/current SoC, technical output/input limits, optional actual battery charge power, and an optional writable signed command target.

## Version note
The integration version is aligned in the source tree for this release:

- `manifest.json`: `20260413.1700`
- `const.py`: `20260413.1700`

## Credits
Owner and publisher: **Q14siX**
