"""Helpers for selecting and converting source sensors."""

from __future__ import annotations

from typing import Final

from homeassistant.core import HomeAssistant, State
from homeassistant.util import slugify

ESC_INTERNAL_ENTITY_PREFIXES: Final[tuple[str, ...]] = (
    "sensor.esc_",
    "number.esc_",
    "binary_sensor.esc_",
    "switch.esc_",
)

POWER_UNIT_FACTORS: Final[dict[str, float]] = {
    "mW": 0.001,
    "W": 1.0,
    "kW": 1000.0,
    "MW": 1_000_000.0,
    "GW": 1_000_000_000.0,
    "TW": 1_000_000_000_000.0,
}


def normalize_entity_ids(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize a config value into a list of entity IDs."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return []


def _coerce_float(value) -> float | None:
    """Convert a value to float when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def is_esc_internal_entity_id(entity_id: str | None) -> bool:
    """Return whether an entity ID belongs to an internally managed ESC entity."""
    if not entity_id:
        return False
    return entity_id.startswith(ESC_INTERNAL_ENTITY_PREFIXES)


def is_esc_internal_state(state: State | None) -> bool:
    """Return whether a state belongs to an internally managed ESC entity."""
    return False if state is None else is_esc_internal_entity_id(state.entity_id)


def is_suitable_power_state(state: State | None) -> bool:
    """Return whether a sensor state is suitable as a grid power source."""
    if state is None or state.domain != "sensor":
        return False

    return is_suitable_power_limit_state(state)


def is_suitable_power_limit_state(state: State | None) -> bool:
    """Return whether an entity state is suitable as a power limit source."""
    if state is None or state.domain not in {"sensor", "number"}:
        return False

    try:
        float(state.state)
    except (TypeError, ValueError):
        return False

    device_class = state.attributes.get("device_class")
    unit = state.attributes.get("unit_of_measurement")

    if isinstance(unit, str) and unit in POWER_UNIT_FACTORS:
        return True

    return device_class == "power"


def state_to_watts(state: State | None) -> float | None:
    """Convert a power-like state to watts."""
    if not is_suitable_power_limit_state(state):
        return None

    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None

    unit = state.attributes.get("unit_of_measurement")
    factor = POWER_UNIT_FACTORS.get(unit, 1.0)
    return round(value * factor, 4)


def get_power_sensor_candidates(hass: HomeAssistant) -> list[str]:
    """Return all selectable power sensor entity IDs."""
    candidates = [
        state.entity_id
        for state in hass.states.async_all("sensor")
        if not is_esc_internal_state(state) and is_suitable_power_state(state)
    ]
    return sorted(candidates, key=slugify)


def is_suitable_soc_entity(state: State | None) -> bool:
    """Return whether an entity is suitable as a state-of-charge source.

    This check is intentionally metadata-focused so configuration is possible
    even when the entity is currently unavailable. It accepts classic battery
    sensors, percentage-based entities and numeric number entities that expose
    a 0-100 range.
    """
    if state is None or state.domain not in {"sensor", "number"}:
        return False

    device_class = state.attributes.get("device_class")
    unit = state.attributes.get("unit_of_measurement")
    if device_class == "battery" or unit == "%":
        return True

    minimum = _coerce_float(state.attributes.get("min"))
    maximum = _coerce_float(state.attributes.get("max"))
    if minimum is None:
        minimum = _coerce_float(state.attributes.get("native_min_value"))
    if maximum is None:
        maximum = _coerce_float(state.attributes.get("native_max_value"))

    if minimum is not None and maximum is not None:
        if -0.0001 <= minimum <= 100.0001 and -0.0001 <= maximum <= 100.0001:
            return True

    value = _coerce_float(state.state)
    if value is not None and 0.0 <= value <= 100.0 and (device_class == "battery" or unit == "%"):
        return True

    return False


def is_suitable_soc_state(state: State | None) -> bool:
    """Return whether a state is suitable and currently numeric for SoC use."""
    if not is_suitable_soc_entity(state):
        return False

    return _coerce_float(state.state) is not None


def state_to_percentage(state: State | None) -> float | None:
    """Convert a state-of-charge state to a percentage value."""
    if not is_suitable_soc_state(state):
        return None

    try:
        return round(float(state.state), 4)
    except (TypeError, ValueError):
        return None


def get_soc_sensor_candidates(hass: HomeAssistant) -> list[str]:
    """Return all selectable SoC entity IDs from sensors and numbers."""
    candidates = [
        state.entity_id
        for state in hass.states.async_all()
        if state.domain in {"sensor", "number"}
        and not is_esc_internal_state(state)
        and is_suitable_soc_entity(state)
    ]
    return sorted(candidates, key=slugify)


def get_power_limit_candidates(hass: HomeAssistant) -> list[str]:
    """Return all selectable power limit entity IDs from sensors and numbers."""
    candidates = [
        state.entity_id
        for state in hass.states.async_all()
        if state.domain in {"sensor", "number"}
        and not is_esc_internal_state(state)
        and is_suitable_power_limit_state(state)
    ]
    return sorted(candidates, key=slugify)


def watts_to_entity_native_value(state: State | None, watts: float) -> float | None:
    """Convert a watt value into the native unit used by a writable target entity."""
    if state is None or state.domain not in {"number", "input_number"}:
        return None

    unit = state.attributes.get("unit_of_measurement")
    if unit in (None, ""):
        return round(float(watts), 4)

    factor = POWER_UNIT_FACTORS.get(unit)
    if factor is None or factor == 0:
        return None

    return round(float(watts) / factor, 4)


def is_suitable_command_target_state(state: State | None) -> bool:
    """Return whether an entity can accept the signed ESC command value.

    The writable target must be able to store both positive and negative values,
    because ESC writes one signed command where charging is negative and
    discharging is positive. A 0..X-only helper would silently clamp negative
    charging commands and can also create self-referential feedback loops when an
    ESC-owned limit entity is selected by mistake.
    """
    if state is None or state.domain not in {"number", "input_number"}:
        return False

    if is_esc_internal_state(state):
        return False

    minimum = _coerce_float(state.attributes.get("min"))
    maximum = _coerce_float(state.attributes.get("max"))
    if minimum is None:
        minimum = _coerce_float(state.attributes.get("native_min_value"))
    if maximum is None:
        maximum = _coerce_float(state.attributes.get("native_max_value"))

    if minimum is None or maximum is None or minimum >= 0 or maximum <= 0:
        return False

    unit = state.attributes.get("unit_of_measurement")
    if unit not in (None, "", *POWER_UNIT_FACTORS.keys()):
        return False

    return True


def get_command_target_candidates(hass: HomeAssistant) -> list[str]:
    """Return writable helper/number entities that can store signed power values."""
    candidates = [
        state.entity_id
        for state in hass.states.async_all()
        if state.domain in {"number", "input_number"}
        and not is_esc_internal_state(state)
        and is_suitable_command_target_state(state)
    ]
    return sorted(candidates, key=slugify)
