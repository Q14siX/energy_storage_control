"""Number platform for Energy Storage Control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BASE_GRID_POWER_STEP,
    BATTERY_CAPACITY_STEP,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_BASE_GRID_POWER_W,
    DEFAULT_SOC_HYSTERESIS_PERCENT,
    DEFAULT_USER_INPUT_LIMIT_W,
    DEFAULT_USER_OUTPUT_LIMIT_W,
    ENTITY_KEY_BASE_GRID_POWER,
    ENTITY_KEY_BATTERY_CAPACITY,
    ENTITY_KEY_FAVORABLE_THRESHOLD,
    ENTITY_KEY_INPUT_POWER_LIMIT,
    ENTITY_KEY_OUTPUT_POWER_LIMIT,
    ENTITY_KEY_SOC_HYSTERESIS,
    MAX_BASE_GRID_POWER_W,
    MAX_BATTERY_CAPACITY_KWH,
    MAX_SOC_HYSTERESIS_PERCENT,
    MAX_THRESHOLD_PERCENT,
    MIN_BASE_GRID_POWER_W,
    MIN_BATTERY_CAPACITY_KWH,
    MIN_SOC_HYSTERESIS_PERCENT,
    MIN_THRESHOLD_PERCENT,
    MIN_USER_POWER_LIMIT_W,
    SOC_HYSTERESIS_STEP,
    THRESHOLD_STEP,
    USER_POWER_LIMIT_STEP,
)
from .coordinator import TibberPreisRuntimeData
from .entity import TibberPreisEntity, TibberPreisGlobalEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[TibberPreisRuntimeData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Energy Storage Control number platform."""
    coordinator = entry.runtime_data.coordinator
    entities = [
        TibberPreisThresholdNumber(coordinator, home_key)
        for home_key in coordinator.home_keys
    ]

    if coordinator.home_keys:
        home_key = coordinator.home_keys[0]
        entities.extend(
            [
                TibberPreisBaseGridPowerNumber(coordinator, home_key),
                TibberPreisBatteryCapacityNumber(coordinator, home_key),
                TibberPreisSocHysteresisNumber(coordinator, home_key),
            ]
        )

        if coordinator.has_power_limit_config:
            entities.extend(
                [
                    TibberPreisOutputPowerLimitNumber(coordinator, home_key),
                    TibberPreisInputPowerLimitNumber(coordinator, home_key),
                ]
            )

    async_add_entities(entities)


class TibberPreisThresholdNumber(TibberPreisEntity, NumberEntity):
    """Configurable percentage threshold used for later price calculations."""

    _attr_translation_key = ENTITY_KEY_FAVORABLE_THRESHOLD
    _attr_icon = "mdi:percent"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_THRESHOLD_PERCENT
    _attr_native_max_value = MAX_THRESHOLD_PERCENT
    _attr_native_step = THRESHOLD_STEP
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{self._device_identifier}_threshold_v2"
        self._set_esc_entity_id("number", 1, "favorable_threshold")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.get_threshold_for_home(self._home_key)

    @property
    def extra_state_attributes(self):
        return self.coordinator.get_favorable_threshold_attributes(self._home_key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_threshold_for_home(self._home_key, value)


class TibberPreisBaseGridPowerNumber(TibberPreisGlobalEntity, NumberEntity):
    """Configurable power that is always drawn from the grid."""

    _attr_translation_key = ENTITY_KEY_BASE_GRID_POWER
    _attr_icon = "mdi:transmission-tower-import"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_BASE_GRID_POWER_W
    _attr_native_max_value = MAX_BASE_GRID_POWER_W
    _attr_native_step = BASE_GRID_POWER_STEP
    _attr_native_unit_of_measurement = "W"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_base_grid_power_v2"
        self._set_esc_entity_id("number", 2, "base_grid_power")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.get_base_grid_power_w() or DEFAULT_BASE_GRID_POWER_W

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_base_grid_power_w(value)


class TibberPreisBatteryCapacityNumber(TibberPreisGlobalEntity, NumberEntity):
    """Configurable maximum battery capacity with derived energy attributes."""

    _attr_translation_key = ENTITY_KEY_BATTERY_CAPACITY
    _attr_icon = "mdi:battery-high"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_BATTERY_CAPACITY_KWH
    _attr_native_max_value = MAX_BATTERY_CAPACITY_KWH
    _attr_native_step = BATTERY_CAPACITY_STEP
    _attr_native_unit_of_measurement = "kWh"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_battery_capacity_v2"
        self._set_esc_entity_id("number", 3, "battery_capacity")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.get_battery_capacity_kwh() or DEFAULT_BATTERY_CAPACITY_KWH

    @property
    def extra_state_attributes(self):
        return self.coordinator.get_battery_capacity_attributes()

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_battery_capacity_kwh(value)


class TibberPreisSocHysteresisNumber(TibberPreisEntity, NumberEntity):
    """Configurable SoC hysteresis percentage to prevent limit chattering."""

    _attr_translation_key = ENTITY_KEY_SOC_HYSTERESIS
    _attr_icon = "mdi:sine-wave"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_SOC_HYSTERESIS_PERCENT
    _attr_native_max_value = MAX_SOC_HYSTERESIS_PERCENT
    _attr_native_step = SOC_HYSTERESIS_STEP
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{self._device_identifier}_soc_hysteresis_percent_v3"
        self._set_esc_entity_id("number", 4, "soc_hysteresis")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.get_soc_hysteresis_percent()

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_soc_hysteresis_percent(value)


class TibberPreisOutputPowerLimitNumber(TibberPreisGlobalEntity, NumberEntity):
    """Configurable user output power limit bounded by the selected source limit."""

    _attr_translation_key = ENTITY_KEY_OUTPUT_POWER_LIMIT
    _attr_icon = "mdi:battery-arrow-down-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_USER_POWER_LIMIT_W
    _attr_native_step = USER_POWER_LIMIT_STEP
    _attr_native_unit_of_measurement = "W"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_output_power_limit_v2"
        self._set_esc_entity_id("number", 5, "user_output_power_limit")

    @property
    def available(self) -> bool:
        return self.coordinator.has_power_limit_config

    @property
    def native_max_value(self) -> float:
        return self.coordinator.get_output_limit_source_value_w() or DEFAULT_USER_OUTPUT_LIMIT_W

    @property
    def native_value(self) -> float:
        return self.coordinator.get_user_output_limit_w() or DEFAULT_USER_OUTPUT_LIMIT_W

    @property
    def extra_state_attributes(self):
        return self.coordinator.get_output_limit_attributes()

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_user_output_limit_w(value)


class TibberPreisInputPowerLimitNumber(TibberPreisGlobalEntity, NumberEntity):
    """Configurable user input power limit bounded by the selected source limit."""

    _attr_translation_key = ENTITY_KEY_INPUT_POWER_LIMIT
    _attr_icon = "mdi:battery-arrow-up-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_USER_POWER_LIMIT_W
    _attr_native_step = USER_POWER_LIMIT_STEP
    _attr_native_unit_of_measurement = "W"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_input_power_limit_v2"
        self._set_esc_entity_id("number", 6, "user_input_power_limit")

    @property
    def available(self) -> bool:
        return self.coordinator.has_power_limit_config

    @property
    def native_max_value(self) -> float:
        return self.coordinator.get_input_limit_source_value_w() or DEFAULT_USER_INPUT_LIMIT_W

    @property
    def native_value(self) -> float:
        return self.coordinator.get_user_input_limit_w() or DEFAULT_USER_INPUT_LIMIT_W

    @property
    def extra_state_attributes(self):
        return self.coordinator.get_input_limit_attributes()

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_user_input_limit_w(value)
