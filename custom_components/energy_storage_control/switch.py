"""Switch platform for Energy Storage Control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ENTITY_KEY_COMMAND_TARGET_UPDATE
from .coordinator import TibberPreisRuntimeData
from .entity import TibberPreisGlobalEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[TibberPreisRuntimeData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Energy Storage Control switch platform."""
    coordinator = entry.runtime_data.coordinator
    if coordinator.home_keys and coordinator.has_command_target_config:
        async_add_entities([TibberPreisCommandTargetUpdateSwitch(coordinator, coordinator.home_keys[0])])


class TibberPreisCommandTargetUpdateSwitch(TibberPreisGlobalEntity, SwitchEntity):
    """Enable or disable updates of the external signed command target."""

    _attr_translation_key = ENTITY_KEY_COMMAND_TARGET_UPDATE
    _attr_icon = "mdi:update"

    def __init__(self, coordinator, home_key: str) -> None:
        super().__init__(coordinator, home_key)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_command_target_update"
        self._set_esc_entity_id("switch", 1, "command_target_update")

    @property
    def available(self) -> bool:
        return self.coordinator.has_command_target_config

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_command_target_update_enabled()

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_command_target_update_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_command_target_update_enabled(False)
