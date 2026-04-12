"""Config flow for Energy Storage Control."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    BASE_GRID_POWER_STEP,
    BATTERY_CAPACITY_STEP,
    CONF_ACTUAL_CHARGE_POWER_SENSOR,
    CONF_COMMAND_TARGET_ENTITY,
    CONF_BASE_GRID_POWER_W,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_DEFAULT_THRESHOLD_PERCENT,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_INPUT_LIMIT_SENSOR,
    CONF_OUTPUT_LIMIT_SENSOR,
    CONF_SOC_CURRENT_SENSOR,
    CONF_SOC_HYSTERESIS_PERCENT,
    CONF_SOC_MAX_SENSOR,
    CONF_SOC_MIN_SENSOR,
    CONF_THRESHOLDS,
    CONF_USER_INPUT_LIMIT_W,
    CONF_USER_OUTPUT_LIMIT_W,
    DEFAULT_BASE_GRID_POWER_W,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_SOC_HYSTERESIS_PERCENT,
    DEFAULT_THRESHOLD_PERCENT,
    DEFAULT_USER_INPUT_LIMIT_W,
    DEFAULT_USER_OUTPUT_LIMIT_W,
    DOMAIN,
    MAX_BASE_GRID_POWER_W,
    MAX_BATTERY_CAPACITY_KWH,
    MAX_SOC_HYSTERESIS_PERCENT,
    MAX_THRESHOLD_PERCENT,
    MIN_BASE_GRID_POWER_W,
    MIN_BATTERY_CAPACITY_KWH,
    MIN_SOC_HYSTERESIS_PERCENT,
    MIN_THRESHOLD_PERCENT,
    MIN_USER_POWER_LIMIT_W,
    NAME,
    SOC_HYSTERESIS_STEP,
    THRESHOLD_STEP,
    USER_POWER_LIMIT_STEP,
)
from .power import (
    get_command_target_candidates,
    get_power_limit_candidates,
    get_power_sensor_candidates,
    get_soc_sensor_candidates,
    is_suitable_soc_entity,
    normalize_entity_ids,
    state_to_watts,
)

REQUIRED_CONFIG_ENTRY_DOMAINS: tuple[str, ...] = ("tibber", "zendure_ha")


def _number_selector(*, min_value: float, max_value: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_value,
            max=max_value,
            step=step,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _entity_selector(*, candidates: list[str], multiple: bool = False, domain: str | list[str] | None = None) -> EntitySelector:
    return EntitySelector(
        EntitySelectorConfig(
            include_entities=candidates,
            multiple=multiple,
            domain=domain,
        )
    )


def _schema_price_settings(default_threshold: float, default_base_load: float) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DEFAULT_THRESHOLD_PERCENT,
                default=round(float(default_threshold), 2),
            ): _number_selector(
                min_value=MIN_THRESHOLD_PERCENT,
                max_value=MAX_THRESHOLD_PERCENT,
                step=THRESHOLD_STEP,
                unit="%",
            ),
            vol.Required(
                CONF_BASE_GRID_POWER_W,
                default=round(float(default_base_load), 2),
            ): _number_selector(
                min_value=MIN_BASE_GRID_POWER_W,
                max_value=MAX_BASE_GRID_POWER_W,
                step=BASE_GRID_POWER_STEP,
                unit="W",
            ),
        }
    )


def _schema_grid_sources(candidates: list[str], import_default: list[str] | None, export_default: list[str] | None) -> vol.Schema:
    selector = _entity_selector(candidates=candidates, multiple=True, domain="sensor")
    return vol.Schema(
        {
            vol.Required(CONF_GRID_IMPORT_SENSOR, default=import_default or []): selector,
            vol.Required(CONF_GRID_EXPORT_SENSOR, default=export_default or []): selector,
        }
    )


def _schema_soc_sources(candidates: list[str], min_default: str | None, max_default: str | None, current_default: str | None) -> vol.Schema:
    selector = _entity_selector(candidates=candidates, domain=["sensor", "number"])
    return vol.Schema(
        {
            vol.Required(CONF_SOC_MIN_SENSOR, default=min_default): selector,
            vol.Required(CONF_SOC_MAX_SENSOR, default=max_default): selector,
            vol.Required(CONF_SOC_CURRENT_SENSOR, default=current_default): selector,
        }
    )


def _schema_charge_feedback_source(candidates: list[str], default_entity: str | None) -> vol.Schema:
    selector = _entity_selector(candidates=candidates, domain=["sensor", "number"])
    return vol.Schema(
        {
            vol.Required(CONF_ACTUAL_CHARGE_POWER_SENSOR, default=default_entity): selector,
        }
    )


def _schema_command_target(candidates: list[str], default_entity: str | None) -> vol.Schema:
    selector = _entity_selector(candidates=candidates, domain=["number", "input_number"])
    return vol.Schema(
        {
            vol.Optional(CONF_COMMAND_TARGET_ENTITY, default=default_entity): selector,
        }
    )


def _schema_battery_settings(default_capacity: float, default_hysteresis: float) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_BATTERY_CAPACITY_KWH,
                default=round(float(default_capacity), 2),
            ): _number_selector(
                min_value=MIN_BATTERY_CAPACITY_KWH,
                max_value=MAX_BATTERY_CAPACITY_KWH,
                step=BATTERY_CAPACITY_STEP,
                unit="kWh",
            ),
            vol.Required(
                CONF_SOC_HYSTERESIS_PERCENT,
                default=round(float(default_hysteresis), 2),
            ): _number_selector(
                min_value=MIN_SOC_HYSTERESIS_PERCENT,
                max_value=MAX_SOC_HYSTERESIS_PERCENT,
                step=SOC_HYSTERESIS_STEP,
                unit="%",
            ),
        }
    )


def _schema_power_limit_sources(candidates: list[str], output_default: str | None, input_default: str | None) -> vol.Schema:
    selector = _entity_selector(candidates=candidates, domain=["sensor", "number"])
    return vol.Schema(
        {
            vol.Required(CONF_OUTPUT_LIMIT_SENSOR, default=output_default): selector,
            vol.Required(CONF_INPUT_LIMIT_SENSOR, default=input_default): selector,
        }
    )


def _schema_user_limits(output_max: float, input_max: float, output_default: float, input_default: float) -> vol.Schema:
    safe_output_max = max(MIN_USER_POWER_LIMIT_W, round(float(output_max), 2))
    safe_input_max = max(MIN_USER_POWER_LIMIT_W, round(float(input_max), 2))
    return vol.Schema(
        {
            vol.Required(
                CONF_USER_OUTPUT_LIMIT_W,
                default=min(round(float(output_default), 2), safe_output_max),
            ): _number_selector(
                min_value=MIN_USER_POWER_LIMIT_W,
                max_value=safe_output_max,
                step=USER_POWER_LIMIT_STEP,
                unit="W",
            ),
            vol.Required(
                CONF_USER_INPUT_LIMIT_W,
                default=min(round(float(input_default), 2), safe_input_max),
            ): _number_selector(
                min_value=MIN_USER_POWER_LIMIT_W,
                max_value=safe_input_max,
                step=USER_POWER_LIMIT_STEP,
                unit="W",
            ),
        }
    )


def _has_invalid_soc_selection(hass, user_input: dict[str, Any]) -> bool:
    entity_ids = [
        user_input.get(CONF_SOC_MIN_SENSOR),
        user_input.get(CONF_SOC_MAX_SENSOR),
        user_input.get(CONF_SOC_CURRENT_SENSOR),
    ]
    for entity_id in entity_ids:
        if not entity_id or not is_suitable_soc_entity(hass.states.get(entity_id)):
            return True
    return False


def _has_duplicate_soc_selection(user_input: dict[str, Any]) -> bool:
    values = [
        user_input.get(CONF_SOC_MIN_SENSOR),
        user_input.get(CONF_SOC_MAX_SENSOR),
        user_input.get(CONF_SOC_CURRENT_SENSOR),
    ]
    values = [value for value in values if value]
    return len(values) != len(set(values))


def _grid_sensor_lists_overlap(user_input: dict[str, Any]) -> bool:
    imports = set(normalize_entity_ids(user_input.get(CONF_GRID_IMPORT_SENSOR)))
    exports = set(normalize_entity_ids(user_input.get(CONF_GRID_EXPORT_SENSOR)))
    return bool(imports & exports)

def _grid_import_missing(user_input: dict[str, Any]) -> bool:
    """Return True if no grid import source was selected."""
    imports = normalize_entity_ids(user_input.get(CONF_GRID_IMPORT_SENSOR))
    return len(imports) == 0



def _power_limit_sources_overlap(user_input: dict[str, Any]) -> bool:
    output_entity = user_input.get(CONF_OUTPUT_LIMIT_SENSOR)
    input_entity = user_input.get(CONF_INPUT_LIMIT_SENSOR)
    return bool(output_entity and input_entity and output_entity == input_entity)


def _get_entity_watts(hass, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    return state_to_watts(hass.states.get(entity_id))


def _invalid_charge_feedback_entity(hass, entity_id: str | None) -> bool:
    return _get_entity_watts(hass, entity_id) is None


def _invalid_command_target_entity(hass, entity_id: str | None) -> bool:
    from .power import is_suitable_command_target_state

    if not entity_id:
        return False
    return not is_suitable_command_target_state(hass.states.get(entity_id))


class EscBaseFlow:
    """Shared helper methods for config and options flows."""

    hass: Any
    _data: dict[str, Any]

    def _requirements_missing(self) -> bool:
        return any(not self.hass.config_entries.async_entries(domain) for domain in REQUIRED_CONFIG_ENTRY_DOMAINS)

    async def _show_requirements_or_next(self):
        if not self._requirements_missing():
            return await self.async_step_price_settings()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}), errors={})

    async def async_step_price_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_DEFAULT_THRESHOLD_PERCENT] = round(float(user_input[CONF_DEFAULT_THRESHOLD_PERCENT]), 2)
            self._data[CONF_BASE_GRID_POWER_W] = round(float(user_input[CONF_BASE_GRID_POWER_W]), 2)
            return await self.async_step_grid_sources()

        return self.async_show_form(
            step_id="price_settings",
            data_schema=_schema_price_settings(
                self._data.get(CONF_DEFAULT_THRESHOLD_PERCENT, DEFAULT_THRESHOLD_PERCENT),
                self._data.get(CONF_BASE_GRID_POWER_W, DEFAULT_BASE_GRID_POWER_W),
            ),
            errors={},
        )

    async def async_step_grid_sources(self, user_input: dict[str, Any] | None = None):
        candidates = get_power_sensor_candidates(self.hass)
        errors: dict[str, str] = {}

        if not candidates:
            errors["base"] = "no_suitable_power_sensors"
        elif user_input is not None:
            if _grid_import_missing(user_input):
                errors["base"] = "grid_import_required"
            elif _grid_sensor_lists_overlap(user_input):
                errors["base"] = "same_sensor_selected"
            else:
                self._data[CONF_GRID_IMPORT_SENSOR] = normalize_entity_ids(user_input.get(CONF_GRID_IMPORT_SENSOR))
                self._data[CONF_GRID_EXPORT_SENSOR] = normalize_entity_ids(user_input.get(CONF_GRID_EXPORT_SENSOR))
                return await self.async_step_soc_sources()

        return self.async_show_form(
            step_id="grid_sources",
            data_schema=_schema_grid_sources(
                candidates,
                normalize_entity_ids(self._data.get(CONF_GRID_IMPORT_SENSOR)),
                normalize_entity_ids(self._data.get(CONF_GRID_EXPORT_SENSOR)),
            ),
            errors=errors,
        )

    async def async_step_soc_sources(self, user_input: dict[str, Any] | None = None):
        candidates = get_soc_sensor_candidates(self.hass)
        errors: dict[str, str] = {}

        if not candidates:
            errors["base"] = "no_suitable_soc_sensors"
        elif user_input is not None:
            if _has_invalid_soc_selection(self.hass, user_input):
                errors["base"] = "invalid_soc_sensor_selected"
            elif _has_duplicate_soc_selection(user_input):
                errors["base"] = "same_soc_sensor_selected"
            else:
                self._data[CONF_SOC_MIN_SENSOR] = user_input[CONF_SOC_MIN_SENSOR]
                self._data[CONF_SOC_MAX_SENSOR] = user_input[CONF_SOC_MAX_SENSOR]
                self._data[CONF_SOC_CURRENT_SENSOR] = user_input[CONF_SOC_CURRENT_SENSOR]
                return await self.async_step_charge_feedback_source()

        return self.async_show_form(
            step_id="soc_sources",
            data_schema=_schema_soc_sources(
                candidates,
                self._data.get(CONF_SOC_MIN_SENSOR),
                self._data.get(CONF_SOC_MAX_SENSOR),
                self._data.get(CONF_SOC_CURRENT_SENSOR),
            ),
            errors=errors,
        )

    async def async_step_charge_feedback_source(self, user_input: dict[str, Any] | None = None):
        candidates = get_power_limit_candidates(self.hass)
        errors: dict[str, str] = {}

        if not candidates:
            errors["base"] = "no_suitable_charge_feedback_entities"
        elif user_input is not None:
            selected = user_input.get(CONF_ACTUAL_CHARGE_POWER_SENSOR)
            if _invalid_charge_feedback_entity(self.hass, selected):
                errors["base"] = "invalid_charge_feedback_entity_selected"
            else:
                self._data[CONF_ACTUAL_CHARGE_POWER_SENSOR] = selected
                return await self.async_step_battery_settings()

        return self.async_show_form(
            step_id="charge_feedback_source",
            data_schema=_schema_charge_feedback_source(
                candidates,
                self._data.get(CONF_ACTUAL_CHARGE_POWER_SENSOR),
            ),
            errors=errors,
        )

    async def async_step_battery_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_BATTERY_CAPACITY_KWH] = round(float(user_input[CONF_BATTERY_CAPACITY_KWH]), 2)
            self._data[CONF_SOC_HYSTERESIS_PERCENT] = round(float(user_input[CONF_SOC_HYSTERESIS_PERCENT]), 2)
            return await self.async_step_power_limit_sources()

        return self.async_show_form(
            step_id="battery_settings",
            data_schema=_schema_battery_settings(
                self._data.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH),
                self._data.get(CONF_SOC_HYSTERESIS_PERCENT, DEFAULT_SOC_HYSTERESIS_PERCENT),
            ),
            errors={},
        )

    async def async_step_power_limit_sources(self, user_input: dict[str, Any] | None = None):
        candidates = get_power_limit_candidates(self.hass)
        errors: dict[str, str] = {}

        if not candidates:
            errors["base"] = "no_suitable_power_limit_entities"
        elif user_input is not None:
            output_entity = user_input.get(CONF_OUTPUT_LIMIT_SENSOR)
            input_entity = user_input.get(CONF_INPUT_LIMIT_SENSOR)
            if _power_limit_sources_overlap(user_input):
                errors["base"] = "same_power_limit_entity_selected"
            elif _get_entity_watts(self.hass, output_entity) is None or _get_entity_watts(self.hass, input_entity) is None:
                errors["base"] = "invalid_power_limit_entity_selected"
            else:
                self._data[CONF_OUTPUT_LIMIT_SENSOR] = output_entity
                self._data[CONF_INPUT_LIMIT_SENSOR] = input_entity
                return await self.async_step_user_limits()

        return self.async_show_form(
            step_id="power_limit_sources",
            data_schema=_schema_power_limit_sources(
                candidates,
                self._data.get(CONF_OUTPUT_LIMIT_SENSOR),
                self._data.get(CONF_INPUT_LIMIT_SENSOR),
            ),
            errors=errors,
        )

    async def async_step_user_limits(self, user_input: dict[str, Any] | None = None):
        output_max = _get_entity_watts(self.hass, self._data.get(CONF_OUTPUT_LIMIT_SENSOR)) or DEFAULT_USER_OUTPUT_LIMIT_W
        input_max = _get_entity_watts(self.hass, self._data.get(CONF_INPUT_LIMIT_SENSOR)) or DEFAULT_USER_INPUT_LIMIT_W

        if user_input is not None:
            self._data[CONF_USER_OUTPUT_LIMIT_W] = round(float(user_input[CONF_USER_OUTPUT_LIMIT_W]), 2)
            self._data[CONF_USER_INPUT_LIMIT_W] = round(float(user_input[CONF_USER_INPUT_LIMIT_W]), 2)
            return await self.async_step_command_target()

        return self.async_show_form(
            step_id="user_limits",
            data_schema=_schema_user_limits(
                output_max,
                input_max,
                self._data.get(CONF_USER_OUTPUT_LIMIT_W, output_max),
                self._data.get(CONF_USER_INPUT_LIMIT_W, input_max),
            ),
            errors={},
        )

    async def async_step_command_target(self, user_input: dict[str, Any] | None = None):
        candidates = get_command_target_candidates(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get(CONF_COMMAND_TARGET_ENTITY)
            if selected and (
                _invalid_command_target_entity(self.hass, selected)
                or selected in {
                    self._data.get(CONF_OUTPUT_LIMIT_SENSOR),
                    self._data.get(CONF_INPUT_LIMIT_SENSOR),
                }
            ):
                errors["base"] = "invalid_command_target_entity_selected"
            else:
                self._data[CONF_COMMAND_TARGET_ENTITY] = selected
                return await self._finish_flow()

        return self.async_show_form(
            step_id="command_target",
            data_schema=_schema_command_target(
                candidates,
                self._data.get(CONF_COMMAND_TARGET_ENTITY),
            ),
            errors=errors,
        )


class TibberPreisConfigFlow(EscBaseFlow, config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Storage Control."""

    VERSION = 1
    MINOR_VERSION = 10

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return TibberPreisOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None and self._requirements_missing():
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "missing_required_integrations"},
            )

        return await self._show_requirements_or_next()

    async def _finish_flow(self):
        return self.async_create_entry(title=NAME, data=self._data)


class TibberPreisOptionsFlow(EscBaseFlow, config_entries.OptionsFlowWithReload):
    """Handle options for Energy Storage Control."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _current_value(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            return self._data[key]
        if key in self.config_entry.options:
            return self.config_entry.options[key]
        return self.config_entry.data.get(key, default)

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        self._data = {
            CONF_DEFAULT_THRESHOLD_PERCENT: self._current_value(CONF_DEFAULT_THRESHOLD_PERCENT, DEFAULT_THRESHOLD_PERCENT),
            CONF_BASE_GRID_POWER_W: self._current_value(CONF_BASE_GRID_POWER_W, DEFAULT_BASE_GRID_POWER_W),
            CONF_GRID_IMPORT_SENSOR: normalize_entity_ids(self._current_value(CONF_GRID_IMPORT_SENSOR, [])),
            CONF_GRID_EXPORT_SENSOR: normalize_entity_ids(self._current_value(CONF_GRID_EXPORT_SENSOR, [])),
            CONF_SOC_MIN_SENSOR: self._current_value(CONF_SOC_MIN_SENSOR),
            CONF_SOC_MAX_SENSOR: self._current_value(CONF_SOC_MAX_SENSOR),
            CONF_SOC_CURRENT_SENSOR: self._current_value(CONF_SOC_CURRENT_SENSOR),
            CONF_ACTUAL_CHARGE_POWER_SENSOR: self._current_value(CONF_ACTUAL_CHARGE_POWER_SENSOR),
            CONF_BATTERY_CAPACITY_KWH: self._current_value(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH),
            CONF_SOC_HYSTERESIS_PERCENT: self._current_value(CONF_SOC_HYSTERESIS_PERCENT, DEFAULT_SOC_HYSTERESIS_PERCENT),
            CONF_OUTPUT_LIMIT_SENSOR: self._current_value(CONF_OUTPUT_LIMIT_SENSOR),
            CONF_INPUT_LIMIT_SENSOR: self._current_value(CONF_INPUT_LIMIT_SENSOR),
            CONF_USER_OUTPUT_LIMIT_W: self._current_value(CONF_USER_OUTPUT_LIMIT_W, DEFAULT_USER_OUTPUT_LIMIT_W),
            CONF_USER_INPUT_LIMIT_W: self._current_value(CONF_USER_INPUT_LIMIT_W, DEFAULT_USER_INPUT_LIMIT_W),
            CONF_COMMAND_TARGET_ENTITY: self._current_value(CONF_COMMAND_TARGET_ENTITY),
        }
        return await self.async_step_price_settings()

    async def _finish_flow(self):
        new_options = dict(self.config_entry.options)
        for key, value in self._data.items():
            if key == CONF_THRESHOLDS:
                continue
            new_options[key] = value
        if CONF_THRESHOLDS in self.config_entry.options:
            new_options[CONF_THRESHOLDS] = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        return self.async_create_entry(data=new_options)
