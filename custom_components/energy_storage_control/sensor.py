"""Sensor platform for Energy Storage Control."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ENTITY_KEY_CHARGE_DISCHARGE_POWER,
    ENTITY_KEY_CURRENT_PRICE,
    ENTITY_KEY_FAVORABLE_PHASE,
    ENTITY_KEY_GRID_POWER_BALANCE,
    ENTITY_KEY_STATE_OF_CHARGE,
)
from .coordinator import TibberPreisRuntimeData
from .entity import TibberPreisEntity, TibberPreisGlobalEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[TibberPreisRuntimeData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Energy Storage Control sensor platform."""
    coordinator = entry.runtime_data.coordinator
    entities = []
    for home_key in coordinator.home_keys:
        entities.extend(
            [
                TibberPreisCurrentPriceSensor(coordinator, home_key),
                TibberPreisFavorablePhaseSensor(coordinator, home_key),
            ]
        )

    if coordinator.has_soc_config and coordinator.home_keys:
        entities.append(TibberPreisStateOfChargeSensor(coordinator, coordinator.home_keys[0]))

    if coordinator.has_grid_power_config and coordinator.home_keys:
        entities.append(
            TibberPreisGridPowerBalanceSensor(coordinator, coordinator.home_keys[0])
        )

    if coordinator.home_keys:
        entities.append(
            TibberPreisChargeDischargePowerSensor(coordinator, coordinator.home_keys[0])
        )

    async_add_entities(entities)


class TibberPreisCurrentPriceSensor(TibberPreisEntity, SensorEntity):
    """Expose the current Tibber price and derived statistics."""

    _attr_translation_key = ENTITY_KEY_CURRENT_PRICE
    _attr_icon = "mdi:currency-eur"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4
    _attr_native_unit_of_measurement = "€/kWh"

    def __init__(self, coordinator, home_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{self._device_identifier}_current_price"
        self._set_esc_entity_id("sensor", 1, "current_price")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return bool(self.coordinator.data.get(self._home_key))

    @property
    def native_value(self) -> float | None:
        """Return the current electricity price."""
        return self.coordinator.get_current_price(self._home_key)

    @property
    def extra_state_attributes(self):
        """Return ordered sensor attributes."""
        return self.coordinator.get_price_attributes(self._home_key)


class TibberPreisFavorablePhaseSensor(TibberPreisEntity, SensorEntity):
    """Expose the start of the current or next favorable phase."""

    _attr_translation_key = ENTITY_KEY_FAVORABLE_PHASE
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, home_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{self._device_identifier}_next_favorable_start"
        self._set_esc_entity_id("sensor", 2, "favorable_phase")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return bool(self.coordinator.data.get(self._home_key))

    @property
    def native_value(self) -> datetime | None:
        """Return the start of the current or next favorable block."""
        return self.coordinator.get_favorable_phase_start(self._home_key)

    @property
    def extra_state_attributes(self):
        """Return ordered phase attributes for the favorable block."""
        return self.coordinator.get_favorable_phase_attributes(self._home_key)


class TibberPreisGridPowerBalanceSensor(TibberPreisGlobalEntity, SensorEntity):
    """Expose the signed grid power balance."""

    _attr_translation_key = ENTITY_KEY_GRID_POWER_BALANCE
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, coordinator, home_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_grid_power_balance"
        self._set_esc_entity_id("sensor", 4, "grid_power_balance")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.get_grid_power_balance_value() is not None

    @property
    def native_value(self) -> float | None:
        """Return the current signed grid power in watts."""
        return self.coordinator.get_grid_power_balance_value()

    @property
    def extra_state_attributes(self):
        """Return the current-day statistics for the grid power balance."""
        return self.coordinator.get_grid_power_balance_attributes()


class TibberPreisStateOfChargeSensor(TibberPreisGlobalEntity, SensorEntity):
    """Expose the current state of charge with configured bounds."""

    _attr_translation_key = ENTITY_KEY_STATE_OF_CHARGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:battery-medium"

    def __init__(self, coordinator, home_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_state_of_charge"
        self._set_esc_entity_id("sensor", 3, "state_of_charge")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.get_current_soc() is not None

    @property
    def native_value(self) -> int | None:
        """Return the current state of charge as a whole-number percentage."""
        return self.coordinator.get_current_soc()

    @property
    def extra_state_attributes(self):
        """Return configured SoC boundaries."""
        return self.coordinator.get_state_of_charge_attributes()


class TibberPreisChargeDischargePowerSensor(TibberPreisGlobalEntity, SensorEntity):
    """Expose the future charge/discharge command value and its derived discharge power."""

    _attr_translation_key = ENTITY_KEY_CHARGE_DISCHARGE_POWER
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W"
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:battery-sync"

    def __init__(self, coordinator, home_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_charge_discharge_power"
        self._set_esc_entity_id("sensor", 5, "charge_discharge_power")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return True

    @property
    def native_value(self) -> float:
        """Return the currently calculated charge/discharge command in watts."""
        value = self.coordinator.get_charge_discharge_power_value()
        return 0.0 if value is None else value

    @property
    def extra_state_attributes(self):
        """Return attributes for the charge/discharge command."""
        return self.coordinator.get_charge_discharge_power_attributes()
