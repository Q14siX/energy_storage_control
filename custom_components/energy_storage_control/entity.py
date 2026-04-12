"""Base entities for Energy Storage Control."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import TibberPreisCoordinator


class TibberPreisEntity(CoordinatorEntity[TibberPreisCoordinator]):
    """Base entity for Energy Storage Control home-specific entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TibberPreisCoordinator, home_key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._home_key = home_key
        self._home_slug = slugify(home_key)
        self._device_identifier = f"{coordinator.config_entry.entry_id}_{self._home_slug}"

    def _set_esc_entity_id(self, platform_domain: str, order: int, suffix: str) -> None:
        """Set a stable entity_id with an esc_ prefix for easier discovery."""
        self.entity_id = f"{platform_domain}.esc_{self._home_slug}_{suffix}"

    @property
    def available(self) -> bool:
        """Return whether the entity itself is available.

        Most ESC entities expose locally derived values or cached data and should
        remain available even if a Tibber refresh temporarily fails.
        """
        return True

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_identifier)},
            "name": self._home_key,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "configuration_url": "https://www.home-assistant.io/integrations/tibber/",
        }


class TibberPreisGlobalEntity(TibberPreisEntity):
    """Base entity for integration-wide entities bound to the primary Tibber home device."""

    def __init__(self, coordinator: TibberPreisCoordinator, home_key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, home_key)
