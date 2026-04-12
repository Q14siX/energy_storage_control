"""Binary sensor platform for Energy Storage Control."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ENTITY_KEY_FAVORABLE_NOW
from .coordinator import TibberPreisRuntimeData
from .entity import TibberPreisEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[TibberPreisRuntimeData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Energy Storage Control binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        TibberPreisFavorableNowBinarySensor(coordinator, home_key)
        for home_key in coordinator.home_keys
    )


class TibberPreisFavorableNowBinarySensor(TibberPreisEntity, BinarySensorEntity):
    """Show whether the current slot is favorable."""

    _attr_translation_key = ENTITY_KEY_FAVORABLE_NOW
    _attr_icon = "mdi:cash-check"

    def __init__(self, coordinator, home_key: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{self._device_identifier}_favorable_now"
        self._set_esc_entity_id("binary_sensor", 1, "favorable_now")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return bool(self.coordinator.data.get(self._home_key))

    @property
    def is_on(self) -> bool:
        """Return whether the current time is favorable."""
        return self.coordinator.is_current_favorable(self._home_key)
