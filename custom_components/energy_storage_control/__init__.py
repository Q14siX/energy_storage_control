"""The Energy Storage Control integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN, PLATFORMS
from .coordinator import TibberPreisCoordinator, TibberPreisRuntimeData

_LOGGER = logging.getLogger(__name__)


TibberPreisConfigEntry = ConfigEntry[TibberPreisRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TibberPreisConfigEntry) -> bool:
    """Set up Energy Storage Control from a config entry."""
    if not hass.config_entries.async_entries("tibber"):
        raise ConfigEntryError(
            "The official Tibber integration must be configured before Energy Storage Control."
        )

    coordinator = TibberPreisCoordinator(hass, entry)
    await coordinator.async_initialize()

    if not coordinator.home_keys:
        try:
            await coordinator.async_update_prices()
        except Exception as err:  # pragma: no cover - defensive, method handles its own errors
            raise ConfigEntryNotReady("Initial Tibber price fetch failed") from err

    if not coordinator.home_keys:
        raise ConfigEntryNotReady("No Tibber homes available yet")

    await _async_remove_legacy_entities(hass, entry, coordinator.home_keys)

    entry.runtime_data = TibberPreisRuntimeData(coordinator=coordinator)
    entry.async_on_unload(await coordinator.async_start())
    await coordinator.async_update_prices()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Energy Storage Control setup finished for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TibberPreisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_remove_legacy_entities(
    hass: HomeAssistant,
    entry: TibberPreisConfigEntry,
    home_keys: list[str],
) -> None:
    """Remove entities that no longer exist in the integration."""
    registry = er.async_get(hass)
    for home_key in home_keys:
        device_identifier = f"{entry.entry_id}_{slugify(home_key)}"
        legacy_unique_id = f"{device_identifier}_favorable_until"
        if entity_id := registry.async_get_entity_id("sensor", DOMAIN, legacy_unique_id):
            registry.async_remove(entity_id)
