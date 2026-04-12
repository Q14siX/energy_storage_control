"""Coordinator for the Energy Storage Control integration."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import logging
from statistics import mean
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CHARGE_EFFICIENCY,
    ATTR_CHARGE_POWER,
    ATTR_CHARGE_EFFICIENCY_CURRENT,
    ATTR_CHARGE_EFFICIENCY_SAMPLES,
    ATTR_COMMAND_TARGET_ENTITY,
    ATTR_COMMAND_TARGET_UPDATE_ENABLED,
    ATTR_CURRENT_ENERGY,
    ATTR_DATA,
    ATTR_DISCHARGE_POWER,
    ATTR_ENERGY_AT_MAXIMUM_SOC,
    ATTR_ENERGY_AT_MINIMUM_SOC,
    ATTR_FAVORABLE_FROM,
    ATTR_FAVORABLE_UNTIL,
    ATTR_GRID_EXPORT,
    ATTR_GRID_IMPORT,
    ATTR_INPUT_LIMIT_SOURCE_VALUE,
    ATTR_OUTPUT_LIMIT_SOURCE_VALUE,
    ATTR_MAXIMUM_SOC,
    ATTR_MINIMUM_SOC,
    ATTR_THRESHOLD_MAX_PRICE,
    ATTR_THRESHOLD_MIN_PRICE,
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
    CONF_SOC_MAX_SENSOR,
    CONF_SOC_MIN_SENSOR,
    CONF_THRESHOLDS,
    CONF_USER_INPUT_LIMIT_W,
    CONF_USER_OUTPUT_LIMIT_W,
    CONF_SOC_HYSTERESIS_PERCENT,
    DEFAULT_BASE_GRID_POWER_W,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_CHARGE_EFFICIENCY_PERCENT,
    DEFAULT_SOC_HYSTERESIS_PERCENT,
    DEFAULT_USER_INPUT_LIMIT_W,
    DEFAULT_USER_OUTPUT_LIMIT_W,
    DOMAIN,
    MAX_VALID_CHARGE_EFFICIENCY_PERCENT,
    MIN_CHARGE_EFFICIENCY_DURATION_SECONDS,
    MIN_CHARGE_EFFICIENCY_REQUESTED_ENERGY_KWH,
    MIN_CHARGE_EFFICIENCY_STORED_ENERGY_KWH,
    MIN_VALID_CHARGE_EFFICIENCY_PERCENT,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .power import (
    is_esc_internal_entity_id,
    normalize_entity_ids,
    state_to_percentage,
    state_to_watts,
    watts_to_entity_native_value,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TibberPreisRuntimeData:
    """Runtime data for the config entry."""

    coordinator: "TibberPreisCoordinator"


class TibberPreisCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Coordinate Tibber price data retrieval, caching and derived values."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.config_entry = config_entry
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{config_entry.entry_id}",
        )
        self.data: dict[str, list[dict[str, Any]]] = {}
        self._grid_power_stats: dict[str, Any] = {}
        self._power_command_state: dict[str, Any] = {
            "charge_discharge_power_w": 0.0,
            "charge_power_w": 0.0,
            "discharge_power_w": 0.0,
            "charge_hold_until_below_hysteresis": False,
            "charge_hold_phase_id": None,
            "charge_efficiency_percent": DEFAULT_CHARGE_EFFICIENCY_PERCENT,
            "charge_efficiency_current_percent": None,
            "charge_efficiency_sample_count": 0,
            "command_target_update_enabled": False,
            "last_processed_discharge_grid_balance_w": None,
            "last_processed_discharge_base_grid_power_w": None,
        }
        self._charge_efficiency_session: dict[str, Any] | None = None
        self._grid_stats_save_unsub: callback | None = None
        self._command_target_sync_unsub: callback | None = None
        self._last_command_target_native_value: float | None = None

    @property
    def home_keys(self) -> list[str]:
        """Return all known Tibber home keys."""
        return list(self.data.keys())

    @property
    def has_grid_power_config(self) -> bool:
        """Return whether the grid power balance sensor is configured."""
        return bool(self.get_grid_import_sensor_entity_ids())

    @property
    def has_soc_config(self) -> bool:
        """Return whether all required SoC sensors are configured."""
        return all(
            (
                self.get_soc_min_sensor_entity_id(),
                self.get_soc_max_sensor_entity_id(),
                self.get_soc_current_sensor_entity_id(),
            )
        )

    @property
    def has_power_limit_config(self) -> bool:
        """Return whether input and output power limit entities are configured."""
        return all((self.get_output_limit_sensor_entity_id(), self.get_input_limit_sensor_entity_id()))

    @property
    def has_charge_feedback_config(self) -> bool:
        """Return whether an actual battery charge-power entity is configured."""
        return bool(self.get_actual_charge_power_sensor_entity_id())

    async def async_initialize(self) -> None:
        """Load cached data from storage."""
        stored = await self._store.async_load()
        if not stored:
            return

        homes = stored.get("homes")
        if isinstance(homes, dict):
            self.data = {
                str(home_key): self._normalize_price_rows(rows)
                for home_key, rows in homes.items()
                if isinstance(rows, list)
            }
            if self.data:
                self.last_update_success = True

        grid_stats = stored.get("grid_power_stats")
        if isinstance(grid_stats, dict):
            self._grid_power_stats = dict(grid_stats)

        power_command_state = stored.get("power_command_state")
        if isinstance(power_command_state, dict):
            self._power_command_state.update(dict(power_command_state))

        # Reset volatile live-regulation values. These are derived from current
        # measurements and must not be restored from an outdated cached state.
        self._power_command_state["charge_discharge_power_w"] = 0.0
        self._power_command_state["charge_power_w"] = 0.0
        self._power_command_state["discharge_power_w"] = 0.0
        self._power_command_state["charge_hold_until_below_hysteresis"] = False
        self._power_command_state["charge_hold_phase_id"] = None
        self._power_command_state["last_processed_discharge_grid_balance_w"] = None
        self._power_command_state["last_processed_discharge_base_grid_power_w"] = None

        self._refresh_power_command_in_memory()

    async def async_start(self) -> callback:
        """Start scheduled refreshes and listeners."""
        unsubscribers: list[callback] = []

        @callback
        def _schedule_price_refresh(now) -> None:
            self.hass.async_create_task(self.async_update_prices())

        @callback
        def _schedule_grid_day_reset(now) -> None:
            self.hass.async_create_task(self.async_reset_grid_stats_for_new_day())

        unsubscribers.append(
            async_track_time_change(
                self.hass,
                _schedule_price_refresh,
                minute=[0, 15, 30, 45],
                second=0,
            )
        )
        unsubscribers.append(
            async_track_time_change(
                self.hass,
                _schedule_grid_day_reset,
                hour=0,
                minute=0,
                second=0,
            )
        )

        if self.has_grid_power_config:
            tracked = list({
                *self.get_grid_import_sensor_entity_ids(),
                *self.get_grid_export_sensor_entity_ids(),
            })

            @callback
            def _handle_grid_source_change(event: Event) -> None:
                self._refresh_grid_power_from_states_in_memory()
                self._schedule_grid_stats_save()

            unsubscribers.append(
                async_track_state_change_event(
                    self.hass,
                    tracked,
                    _handle_grid_source_change,
                )
            )
            self._refresh_grid_power_from_states_in_memory()
            self._schedule_grid_stats_save()

        if self.has_soc_config:
            tracked_soc = [
                self.get_soc_min_sensor_entity_id(),
                self.get_soc_max_sensor_entity_id(),
                self.get_soc_current_sensor_entity_id(),
            ]
            tracked_soc = [entity_id for entity_id in tracked_soc if entity_id]

            @callback
            def _handle_soc_source_change(event: Event) -> None:
                self._refresh_power_command_in_memory()
                self._schedule_grid_stats_save()

            unsubscribers.append(
                async_track_state_change_event(
                    self.hass,
                    tracked_soc,
                    _handle_soc_source_change,
                )
            )

        if self.has_charge_feedback_config:
            tracked_charge_feedback = [self.get_actual_charge_power_sensor_entity_id()]
            tracked_charge_feedback = [entity_id for entity_id in tracked_charge_feedback if entity_id]

            @callback
            def _handle_charge_feedback_source_change(event: Event) -> None:
                self._refresh_power_command_in_memory()
                self.async_update_listeners()
                self._schedule_grid_stats_save()

            unsubscribers.append(
                async_track_state_change_event(
                    self.hass,
                    tracked_charge_feedback,
                    _handle_charge_feedback_source_change,
                )
            )

        if self.has_power_limit_config:
            tracked_power_limits = [
                self.get_output_limit_sensor_entity_id(),
                self.get_input_limit_sensor_entity_id(),
            ]
            tracked_power_limits = [entity_id for entity_id in tracked_power_limits if entity_id]

            @callback
            def _handle_power_limit_source_change(event: Event) -> None:
                self._refresh_power_command_in_memory()
                self.async_update_listeners()
                self._schedule_grid_stats_save()

            unsubscribers.append(
                async_track_state_change_event(
                    self.hass,
                    tracked_power_limits,
                    _handle_power_limit_source_change,
                )
            )

        @callback
        def _unsubscribe_all() -> None:
            if self._grid_stats_save_unsub is not None:
                self._grid_stats_save_unsub()
                self._grid_stats_save_unsub = None
            if self._command_target_sync_unsub is not None:
                self._command_target_sync_unsub()
                self._command_target_sync_unsub = None
            for unsub in unsubscribers:
                unsub()

        return _unsubscribe_all

    async def async_update_prices(self) -> None:
        """Fetch fresh Tibber prices and update listeners."""
        try:
            latest = await self._async_fetch_prices()
        except Exception as err:  # pylint: disable=broad-except
            self.last_update_success = False
            _LOGGER.warning("Refreshing Tibber prices failed: %s", err)
            self.async_update_listeners()
            return

        self.last_update_success = True
        self.async_set_updated_data(latest)
        self._refresh_power_command_in_memory()
        await self._async_save_store()

    async def async_refresh_grid_power_from_states(self) -> None:
        """Refresh the grid power balance using the configured source sensors."""
        self._refresh_grid_power_from_states_in_memory()
        await self._async_save_store()

    @callback
    def _refresh_grid_power_from_states_in_memory(self) -> None:
        """Refresh the grid power balance in memory and update listeners immediately."""
        if not self.has_grid_power_config:
            return

        current_watts = self._calculate_current_grid_power_watts()
        if current_watts is None:
            self._refresh_power_command_in_memory()
            self.async_update_listeners()
            return

        now = dt_util.now()
        today_str = now.date().isoformat()
        if self._grid_power_stats.get("date") != today_str:
            self._grid_power_stats = self._create_new_grid_stats(today_str, current_watts, now)
        else:
            self._update_grid_stats(current_watts, now)

        self._refresh_power_command_in_memory()
        self.async_update_listeners()

    @callback
    def _schedule_grid_stats_save(self, delay: float = 2.0) -> None:
        """Persist grid stats with a short debounce so live updates stay responsive."""
        if self._grid_stats_save_unsub is not None:
            self._grid_stats_save_unsub()
            self._grid_stats_save_unsub = None

        @callback
        def _run_save(_now) -> None:
            self._grid_stats_save_unsub = None
            self.hass.async_create_task(self._async_save_store())

        self._grid_stats_save_unsub = async_call_later(self.hass, delay, _run_save)

    async def async_reset_grid_stats_for_new_day(self) -> None:
        """Reset grid power statistics at the start of a new local day."""
        if not self.has_grid_power_config:
            return

        now = dt_util.now()
        current_watts = self._calculate_current_grid_power_watts()
        if current_watts is None:
            self._grid_power_stats = {"date": now.date().isoformat()}
        else:
            self._grid_power_stats = self._create_new_grid_stats(
                now.date().isoformat(),
                current_watts,
                now,
            )
        self._refresh_power_command_in_memory()
        await self._async_save_store()
        self.async_update_listeners()

    async def _async_fetch_prices(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch Tibber prices for today and tomorrow."""
        start = dt_util.start_of_local_day()
        end = start + timedelta(days=2)

        response = await self.hass.services.async_call(
            "tibber",
            "get_prices",
            {
                "start": dt_util.as_local(start).strftime("%Y-%m-%d %H:%M:%S"),
                "end": dt_util.as_local(end).strftime("%Y-%m-%d %H:%M:%S"),
            },
            blocking=True,
            return_response=True,
        )

        if not isinstance(response, dict):
            raise RuntimeError("Unexpected response from tibber.get_prices")

        prices = response.get("prices")
        if not isinstance(prices, dict) or not prices:
            raise RuntimeError("No Tibber prices available")

        normalized: dict[str, list[dict[str, Any]]] = {}
        for home_key, rows in prices.items():
            if isinstance(rows, list):
                normalized[str(home_key)] = self._normalize_price_rows(rows)

        if not normalized:
            raise RuntimeError("No valid Tibber homes returned")

        return normalized

    async def _async_save_store(self) -> None:
        """Persist current cached state."""
        await self._store.async_save(
            {
                "homes": self.data,
                "grid_power_stats": self._grid_power_stats,
                "power_command_state": self._power_command_state,
            }
        )

    def get_threshold_for_home(self, home_key: str) -> float:
        """Return the configured threshold for a home."""
        thresholds = self.config_entry.options.get(CONF_THRESHOLDS, {})
        if isinstance(thresholds, dict) and home_key in thresholds:
            try:
                return float(thresholds[home_key])
            except (TypeError, ValueError):
                pass

        return float(
            self.config_entry.options.get(
                CONF_DEFAULT_THRESHOLD_PERCENT,
                self.config_entry.data.get(
                    CONF_DEFAULT_THRESHOLD_PERCENT,
                    20.0,
                ),
            )
        )

    async def async_set_threshold_for_home(self, home_key: str, value: float) -> None:
        """Persist the configured threshold for a home."""
        thresholds = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        thresholds[home_key] = round(float(value), 2)
        new_options = dict(self.config_entry.options)
        new_options[CONF_THRESHOLDS] = dict(thresholds)
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
        self._refresh_power_command_in_memory()
        self.async_update_listeners()
        await self._async_save_store()

    def get_base_grid_power_w(self) -> float:
        """Return the configured power that is always drawn from the grid in watts."""
        raw_value = self.config_entry.options.get(
            CONF_BASE_GRID_POWER_W,
            self.config_entry.data.get(CONF_BASE_GRID_POWER_W, DEFAULT_BASE_GRID_POWER_W),
        )
        try:
            return round(float(raw_value), 4)
        except (TypeError, ValueError):
            return DEFAULT_BASE_GRID_POWER_W

    async def async_set_base_grid_power_w(self, value: float) -> None:
        """Persist the configured base grid power in watts."""
        new_options = dict(self.config_entry.options)
        new_options[CONF_BASE_GRID_POWER_W] = round(float(value), 2)
        if CONF_THRESHOLDS in self.config_entry.options:
            new_options[CONF_THRESHOLDS] = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
        self._refresh_power_command_in_memory()
        self.async_update_listeners()
        await self._async_save_store()

    def get_soc_hysteresis_percent(self) -> float:
        """Return the configured SoC hysteresis percentage."""
        raw_value = self.config_entry.options.get(
            CONF_SOC_HYSTERESIS_PERCENT,
            self.config_entry.data.get(CONF_SOC_HYSTERESIS_PERCENT, DEFAULT_SOC_HYSTERESIS_PERCENT),
        )
        try:
            return round(float(raw_value), 4)
        except (TypeError, ValueError):
            return DEFAULT_SOC_HYSTERESIS_PERCENT

    async def async_set_soc_hysteresis_percent(self, value: float) -> None:
        """Persist the configured SoC hysteresis percentage."""
        new_options = dict(self.config_entry.options)
        new_options[CONF_SOC_HYSTERESIS_PERCENT] = round(float(value), 2)
        if CONF_THRESHOLDS in self.config_entry.options:
            new_options[CONF_THRESHOLDS] = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
        self._refresh_power_command_in_memory()
        self.async_update_listeners()

    def get_battery_capacity_kwh(self) -> float:
        """Return the configured maximum battery capacity in kWh."""
        raw_value = self.config_entry.options.get(
            CONF_BATTERY_CAPACITY_KWH,
            self.config_entry.data.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH),
        )
        try:
            return round(float(raw_value), 4)
        except (TypeError, ValueError):
            return DEFAULT_BATTERY_CAPACITY_KWH

    async def async_set_battery_capacity_kwh(self, value: float) -> None:
        """Persist the configured maximum battery capacity."""
        new_options = dict(self.config_entry.options)
        new_options[CONF_BATTERY_CAPACITY_KWH] = round(float(value), 2)
        if CONF_THRESHOLDS in self.config_entry.options:
            new_options[CONF_THRESHOLDS] = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
        self._refresh_power_command_in_memory()
        self.async_update_listeners()

    def get_grid_import_sensor_entity_ids(self) -> list[str]:
        """Return the configured grid import power sensors."""
        value = self.config_entry.options.get(
            CONF_GRID_IMPORT_SENSOR,
            self.config_entry.data.get(CONF_GRID_IMPORT_SENSOR),
        )
        return normalize_entity_ids(value)

    def get_grid_export_sensor_entity_ids(self) -> list[str]:
        """Return the configured grid export power sensors, if any."""
        value = self.config_entry.options.get(
            CONF_GRID_EXPORT_SENSOR,
            self.config_entry.data.get(CONF_GRID_EXPORT_SENSOR),
        )
        return normalize_entity_ids(value)

    def get_grid_import_sensor_entity_id(self) -> str | None:
        """Return the first configured grid import power sensor."""
        entity_ids = self.get_grid_import_sensor_entity_ids()
        return entity_ids[0] if entity_ids else None

    def get_actual_charge_power_sensor_entity_id(self) -> str | None:
        """Return the configured entity that reports actual charging power into the battery."""
        value = self.config_entry.options.get(
            CONF_ACTUAL_CHARGE_POWER_SENSOR,
            self.config_entry.data.get(CONF_ACTUAL_CHARGE_POWER_SENSOR),
        )
        return str(value) if value else None

    def get_actual_charge_power_value_w(self) -> float | None:
        """Return the selected actual battery charge-power entity value in watts."""
        return self._round_or_none(state_to_watts(self.hass.states.get(self.get_actual_charge_power_sensor_entity_id())))

    def get_command_target_entity_id(self) -> str | None:
        """Return the configured writable entity that should receive the signed ESC command."""
        value = self.config_entry.options.get(
            CONF_COMMAND_TARGET_ENTITY,
            self.config_entry.data.get(CONF_COMMAND_TARGET_ENTITY),
        )
        return str(value) if value else None

    @property
    def has_command_target_config(self) -> bool:
        """Return whether an external writable command target is configured."""
        return bool(self.get_command_target_entity_id())

    def is_command_target_update_enabled(self) -> bool:
        """Return whether external target updates are enabled."""
        if not self.has_command_target_config:
            return False
        return bool(self._power_command_state.get("command_target_update_enabled", False))

    async def async_set_command_target_update_enabled(self, enabled: bool) -> None:
        """Enable or disable updates of the selected external command target."""
        self._power_command_state["command_target_update_enabled"] = bool(enabled)
        self.async_update_listeners()
        await self._async_sync_command_target(force=True)
        await self._async_save_store()

    @callback
    def _schedule_command_target_sync(self, delay: float = 0.0) -> None:
        """Schedule synchronization of the signed command target entity."""
        if self._command_target_sync_unsub is not None:
            self._command_target_sync_unsub()
            self._command_target_sync_unsub = None

        if not self.has_command_target_config:
            return

        @callback
        def _run_sync(_now) -> None:
            self._command_target_sync_unsub = None
            self.hass.async_create_task(self._async_sync_command_target())

        self._command_target_sync_unsub = async_call_later(self.hass, delay, _run_sync)

    async def _async_sync_command_target(self, force: bool = False) -> None:
        """Write the signed ESC command to the configured writable target entity."""
        target_entity_id = self.get_command_target_entity_id()
        if not target_entity_id:
            return

        if is_esc_internal_entity_id(target_entity_id):
            _LOGGER.warning(
                "Skipping unsafe command target sync to internally managed ESC entity %s",
                target_entity_id,
            )
            return

        if target_entity_id in {
            self.get_output_limit_sensor_entity_id(),
            self.get_input_limit_sensor_entity_id(),
        }:
            _LOGGER.warning(
                "Skipping unsafe command target sync because %s is also configured as a power limit source",
                target_entity_id,
            )
            return

        target_state = self.hass.states.get(target_entity_id)
        if target_state is None:
            return

        desired_watts = self.get_charge_discharge_power_value() if self.is_command_target_update_enabled() else 0.0
        native_value = watts_to_entity_native_value(target_state, desired_watts)
        if native_value is None:
            return

        minimum = target_state.attributes.get("min")
        maximum = target_state.attributes.get("max")
        if minimum is None:
            minimum = target_state.attributes.get("native_min_value")
        if maximum is None:
            maximum = target_state.attributes.get("native_max_value")

        try:
            if minimum is not None:
                native_value = max(float(minimum), float(native_value))
            if maximum is not None:
                native_value = min(float(maximum), float(native_value))
        except (TypeError, ValueError):
            pass

        native_value = round(float(native_value), 4)
        if not force and self._last_command_target_native_value is not None:
            if abs(native_value - self._last_command_target_native_value) < 0.0001:
                return

        domain = target_entity_id.split('.', 1)[0]
        service_domain = 'input_number' if domain == 'input_number' else 'number'
        await self.hass.services.async_call(
            service_domain,
            'set_value',
            {
                'entity_id': target_entity_id,
                'value': native_value,
            },
            blocking=True,
        )
        self._last_command_target_native_value = native_value

    def get_output_limit_sensor_entity_id(self) -> str | None:
        """Return the configured output limit entity."""
        value = self.config_entry.options.get(
            CONF_OUTPUT_LIMIT_SENSOR,
            self.config_entry.data.get(CONF_OUTPUT_LIMIT_SENSOR),
        )
        return str(value) if value else None

    def get_input_limit_sensor_entity_id(self) -> str | None:
        """Return the configured input limit entity."""
        value = self.config_entry.options.get(
            CONF_INPUT_LIMIT_SENSOR,
            self.config_entry.data.get(CONF_INPUT_LIMIT_SENSOR),
        )
        return str(value) if value else None

    def get_output_limit_source_value_w(self) -> float | None:
        """Return the selected output limit entity value in watts."""
        entity_id = self.get_output_limit_sensor_entity_id()
        if is_esc_internal_entity_id(entity_id):
            _LOGGER.warning(
                "Ignoring unsafe output limit source because %s is an internally managed ESC entity",
                entity_id,
            )
            return None
        return self._round_or_none(state_to_watts(self.hass.states.get(entity_id)))

    def get_input_limit_source_value_w(self) -> float | None:
        """Return the selected input limit entity value in watts."""
        entity_id = self.get_input_limit_sensor_entity_id()
        if is_esc_internal_entity_id(entity_id):
            _LOGGER.warning(
                "Ignoring unsafe input limit source because %s is an internally managed ESC entity",
                entity_id,
            )
            return None
        return self._round_or_none(state_to_watts(self.hass.states.get(entity_id)))

    def get_user_output_limit_w(self) -> float:
        """Return the configured user output limit in watts, clamped to the current source limit."""
        raw_value = self.config_entry.options.get(
            CONF_USER_OUTPUT_LIMIT_W,
            self.config_entry.data.get(CONF_USER_OUTPUT_LIMIT_W, DEFAULT_USER_OUTPUT_LIMIT_W),
        )
        try:
            value = round(float(raw_value), 4)
        except (TypeError, ValueError):
            value = DEFAULT_USER_OUTPUT_LIMIT_W
        source_value = self.get_output_limit_source_value_w()
        if source_value is None:
            return value
        return round(min(value, source_value), 4)

    async def async_set_user_output_limit_w(self, value: float) -> None:
        """Persist the configured user output limit in watts."""
        source_value = self.get_output_limit_source_value_w()
        if source_value is not None:
            value = min(float(value), source_value)
        new_options = dict(self.config_entry.options)
        new_options[CONF_USER_OUTPUT_LIMIT_W] = round(float(value), 2)
        if CONF_THRESHOLDS in self.config_entry.options:
            new_options[CONF_THRESHOLDS] = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
        self._refresh_power_command_in_memory()
        self.async_update_listeners()
        await self._async_save_store()

    def get_user_input_limit_w(self) -> float:
        """Return the configured user input limit in watts, clamped to the current source limit."""
        raw_value = self.config_entry.options.get(
            CONF_USER_INPUT_LIMIT_W,
            self.config_entry.data.get(CONF_USER_INPUT_LIMIT_W, DEFAULT_USER_INPUT_LIMIT_W),
        )
        try:
            value = round(float(raw_value), 4)
        except (TypeError, ValueError):
            value = DEFAULT_USER_INPUT_LIMIT_W
        source_value = self.get_input_limit_source_value_w()
        if source_value is None:
            return value
        return round(min(value, source_value), 4)

    async def async_set_user_input_limit_w(self, value: float) -> None:
        """Persist the configured user input limit in watts."""
        source_value = self.get_input_limit_source_value_w()
        if source_value is not None:
            value = min(float(value), source_value)
        new_options = dict(self.config_entry.options)
        new_options[CONF_USER_INPUT_LIMIT_W] = round(float(value), 2)
        if CONF_THRESHOLDS in self.config_entry.options:
            new_options[CONF_THRESHOLDS] = dict(self.config_entry.options.get(CONF_THRESHOLDS, {}))
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
        self._refresh_power_command_in_memory()
        self.async_update_listeners()

    def get_output_limit_attributes(self) -> OrderedDict[str, Any]:
        """Return attributes for the configurable user output limit entity."""
        attributes: OrderedDict[str, Any] = OrderedDict()
        attributes[ATTR_OUTPUT_LIMIT_SOURCE_VALUE] = self.get_output_limit_source_value_w()
        return attributes

    def get_input_limit_attributes(self) -> OrderedDict[str, Any]:
        """Return attributes for the configurable user input limit entity."""
        attributes: OrderedDict[str, Any] = OrderedDict()
        attributes[ATTR_INPUT_LIMIT_SOURCE_VALUE] = self.get_input_limit_source_value_w()
        return attributes

    def get_charge_discharge_power_value(self) -> float:
        """Return the current signed charge/discharge command in watts."""
        value = self._power_command_state.get("charge_discharge_power_w", 0.0)
        return self._round_or_none(value) or 0.0

    def get_charge_power_value(self) -> float:
        """Return the current derived charge power in watts."""
        value = self._power_command_state.get("charge_power_w", 0.0)
        return self._round_or_none(value) or 0.0

    def get_discharge_power_value(self) -> float:
        """Return the current derived discharge power in watts."""
        value = self._power_command_state.get("discharge_power_w", 0.0)
        return self._round_or_none(value) or 0.0

    def get_charge_efficiency_percent(self) -> float:
        """Return the learned charge efficiency percentage used for future planning."""
        value = self._power_command_state.get("charge_efficiency_percent", DEFAULT_CHARGE_EFFICIENCY_PERCENT)
        rounded = self._round_or_none(value)
        return DEFAULT_CHARGE_EFFICIENCY_PERCENT if rounded is None else rounded

    def get_charge_efficiency_current_percent(self) -> float | None:
        """Return the most recently measured current charge efficiency percentage."""
        return self._round_or_none(self._power_command_state.get("charge_efficiency_current_percent"))

    def get_charge_efficiency_sample_count(self) -> int:
        """Return the number of accepted charge-efficiency learning samples."""
        try:
            return int(self._power_command_state.get("charge_efficiency_sample_count", 0))
        except (TypeError, ValueError):
            return 0

    def get_charge_discharge_power_attributes(self) -> OrderedDict[str, Any]:
        """Return attributes for the charge/discharge command sensor."""
        attributes: OrderedDict[str, Any] = OrderedDict()
        attributes[ATTR_CHARGE_POWER] = self.get_charge_power_value()
        attributes[ATTR_DISCHARGE_POWER] = self.get_discharge_power_value()
        attributes[ATTR_CHARGE_EFFICIENCY] = self.get_charge_efficiency_percent()
        attributes[ATTR_CHARGE_EFFICIENCY_CURRENT] = self.get_charge_efficiency_current_percent()
        attributes[ATTR_CHARGE_EFFICIENCY_SAMPLES] = self.get_charge_efficiency_sample_count()
        attributes[ATTR_COMMAND_TARGET_ENTITY] = self.get_command_target_entity_id()
        attributes[ATTR_COMMAND_TARGET_UPDATE_ENABLED] = self.is_command_target_update_enabled()
        return attributes

    @callback
    def _refresh_power_command_in_memory(self) -> None:
        """Refresh the derived charge/discharge command values in memory."""
        home_key = self.home_keys[0] if self.home_keys else None

        raw_grid_balance = self.get_grid_power_balance_value()
        base_grid_power = float(self.get_base_grid_power_w())

        # The discharge target must follow the documented ESC rule directly:
        #   discharge_power = max(grid_power_balance - base_grid_power, 0)
        #
        # A previous release tried to reconstruct the "real" house load by
        # adding the last commanded discharge power back onto the measured grid
        # balance. That only works when the command is also a trustworthy live
        # feedback value. In practice the command can be stale, clamped or not
        # yet executed by the external battery logic at all. Then ESC feeds its
        # own old setpoint back into the next calculation and the command can
        # stick to the maximum output limit, even though the live grid balance
        # would only require a small discharge.
        if raw_grid_balance is None:
            discharge_power = 0.0
        else:
            discharge_power = max(float(raw_grid_balance) - base_grid_power, 0.0)

        self._power_command_state["last_processed_discharge_grid_balance_w"] = raw_grid_balance
        self._power_command_state["last_processed_discharge_base_grid_power_w"] = base_grid_power

        current_soc = self.get_current_soc()
        min_soc = self.get_min_soc()
        if current_soc is not None and min_soc is not None and current_soc <= min_soc:
            discharge_power = 0.0

        user_output_limit = self.get_user_output_limit_w()
        if user_output_limit >= 0.0:
            discharge_power = min(discharge_power, user_output_limit)

        charge_power = 0.0
        hold_until_below_hysteresis = bool(
            self._power_command_state.get("charge_hold_until_below_hysteresis", False)
        )
        hold_phase_id = self._power_command_state.get("charge_hold_phase_id")
        current_phase_id = self.get_current_favorable_phase_id(home_key) if home_key else None

        if not current_phase_id:
            hold_until_below_hysteresis = False
            hold_phase_id = None
        else:
            max_soc = self.get_max_soc()
            hysteresis = max(float(self.get_soc_hysteresis_percent()), 0.0)

            if hold_phase_id != current_phase_id:
                hold_until_below_hysteresis = False
                hold_phase_id = None

            if current_soc is not None and max_soc is not None:
                if current_soc >= max_soc:
                    hold_until_below_hysteresis = True
                    hold_phase_id = current_phase_id
                elif current_soc <= (max_soc - hysteresis):
                    hold_until_below_hysteresis = False
                    hold_phase_id = None

            if not hold_until_below_hysteresis:
                charge_power = self._calculate_current_charge_power_w(home_key)

        charge_power = round(float(charge_power), 4)
        discharge_power = round(float(discharge_power), 4)

        if home_key and self.is_current_favorable(home_key):
            charge_discharge_power = -charge_power
        else:
            charge_discharge_power = discharge_power

        self._power_command_state["charge_hold_until_below_hysteresis"] = hold_until_below_hysteresis
        self._power_command_state["charge_hold_phase_id"] = hold_phase_id
        self._power_command_state["charge_power_w"] = charge_power
        self._power_command_state["charge_discharge_power_w"] = round(float(charge_discharge_power), 4)
        self._power_command_state["discharge_power_w"] = discharge_power

        if self._update_charge_efficiency_learning_in_memory():
            self._schedule_grid_stats_save()

        self._schedule_command_target_sync()

    @callback
    def _update_charge_efficiency_learning_in_memory(self) -> bool:
        """Update the learned charge efficiency from finished charging phases.

        The learning framework uses a configured entity for the actual charging
        power into the battery. Learning only happens when that feedback entity
        reports real positive charging power, so no efficiency is learned from a
        mere planned command that was never actually sent to or executed by the battery.
        """
        now = dt_util.now()
        actual_charge_power_w = max(self.get_actual_charge_power_value_w() or 0.0, 0.0)
        current_soc = self.get_current_soc()
        current_energy_kwh = self._calculate_energy_from_soc(current_soc)
        session = self._charge_efficiency_session

        def _finalize_session() -> bool:
            if self._charge_efficiency_session is None:
                return False

            active_session = self._charge_efficiency_session
            self._charge_efficiency_session = None

            start_energy = active_session.get("start_energy_kwh")
            last_energy = active_session.get("last_energy_kwh")
            requested_energy = float(active_session.get("requested_energy_kwh", 0.0) or 0.0)
            start_time = active_session.get("start_time")
            last_time = active_session.get("last_time")

            if start_energy is None or last_energy is None or start_time is None or last_time is None:
                return False

            stored_energy = float(last_energy) - float(start_energy)
            duration_seconds = max((last_time - start_time).total_seconds(), 0.0)

            if requested_energy < MIN_CHARGE_EFFICIENCY_REQUESTED_ENERGY_KWH:
                return False
            if stored_energy < MIN_CHARGE_EFFICIENCY_STORED_ENERGY_KWH:
                return False
            if duration_seconds < MIN_CHARGE_EFFICIENCY_DURATION_SECONDS:
                return False

            efficiency_percent = round((stored_energy / requested_energy) * 100.0, 2)
            if not (MIN_VALID_CHARGE_EFFICIENCY_PERCENT <= efficiency_percent <= MAX_VALID_CHARGE_EFFICIENCY_PERCENT):
                return False

            sample_count = self.get_charge_efficiency_sample_count()
            learned_percent = (
                efficiency_percent
                if sample_count == 0
                else round(
                    ((self.get_charge_efficiency_percent() * sample_count) + efficiency_percent) / (sample_count + 1),
                    2,
                )
            )

            self._power_command_state["charge_efficiency_current_percent"] = efficiency_percent
            self._power_command_state["charge_efficiency_percent"] = learned_percent
            self._power_command_state["charge_efficiency_sample_count"] = sample_count + 1
            return True

        if session is not None:
            last_time = session.get("last_time")
            last_charge_power_w = float(session.get("last_charge_power_w", 0.0) or 0.0)
            if last_time is not None:
                elapsed_hours = max((now - last_time).total_seconds() / 3600.0, 0.0)
                if elapsed_hours > 0.0 and last_charge_power_w > 0.0:
                    session["requested_energy_kwh"] = float(session.get("requested_energy_kwh", 0.0) or 0.0) + (last_charge_power_w / 1000.0 * elapsed_hours)

            session["last_time"] = now
            session["last_charge_power_w"] = actual_charge_power_w
            if current_energy_kwh is not None:
                session["last_energy_kwh"] = current_energy_kwh
            if current_soc is not None:
                session["last_soc"] = current_soc

        if actual_charge_power_w <= 0.0 or current_energy_kwh is None or current_soc is None:
            return _finalize_session()

        if self._charge_efficiency_session is None:
            self._charge_efficiency_session = {
                "start_time": now,
                "start_soc": current_soc,
                "start_energy_kwh": current_energy_kwh,
                "last_time": now,
                "last_soc": current_soc,
                "last_energy_kwh": current_energy_kwh,
                "last_charge_power_w": actual_charge_power_w,
                "requested_energy_kwh": 0.0,
            }

        return False

    def _calculate_current_charge_power_w(self, home_key: str) -> float:
        """Calculate the current charge power in watts for the active favorable phase."""
        if not self.is_current_favorable(home_key):
            return 0.0

        current_soc = self.get_current_soc()
        max_soc = self.get_max_soc()
        battery_capacity_kwh = self.get_battery_capacity_kwh()
        charge_efficiency_percent = self.get_charge_efficiency_percent()
        user_input_limit_w = self.get_user_input_limit_w()

        if (
            current_soc is None
            or max_soc is None
            or battery_capacity_kwh <= 0.0
            or user_input_limit_w <= 0.0
            or charge_efficiency_percent <= 0.0
        ):
            return 0.0

        missing_soc_percent = max(float(max_soc) - float(current_soc), 0.0)
        if missing_soc_percent <= 0.0:
            return 0.0

        required_stored_energy_kwh = battery_capacity_kwh * missing_soc_percent / 100.0
        required_input_energy_kwh = required_stored_energy_kwh / (charge_efficiency_percent / 100.0)
        if required_input_energy_kwh <= 0.0:
            return 0.0

        phase_rows = self.get_favorable_phase_rows(home_key)
        if not phase_rows:
            return 0.0

        parsed = self._parse_rows(self.data.get(home_key, []))
        now = dt_util.now()
        remaining_slots: list[dict[str, float | datetime | int]] = []

        for start, price in phase_rows:
            slot_end = None
            for index, (parsed_start, _) in enumerate(parsed):
                if parsed_start != start:
                    continue
                if (index + 1) < len(parsed):
                    slot_end = parsed[index + 1][0]
                else:
                    slot_end = parsed[index][0] + timedelta(minutes=15)
                break

            if slot_end is None or slot_end <= now:
                continue

            slot_effective_start = max(start, now)
            duration_hours = max((slot_end - slot_effective_start).total_seconds() / 3600.0, 0.0)
            if duration_hours <= 0.0:
                continue

            remaining_slots.append(
                {
                    "start": start,
                    "end": slot_end,
                    "price": float(price),
                    "duration_hours": duration_hours,
                    "max_energy_kwh": (user_input_limit_w / 1000.0) * duration_hours,
                }
            )

        if not remaining_slots:
            return 0.0

        total_possible_energy_kwh = sum(float(slot["max_energy_kwh"]) for slot in remaining_slots)
        if total_possible_energy_kwh <= 0.0:
            return 0.0

        current_slot_candidates = [
            slot
            for slot in remaining_slots
            if slot["start"] <= now < slot["end"]
        ]
        if current_slot_candidates:
            current_slot = current_slot_candidates[0]
        else:
            current_slot = min(remaining_slots, key=lambda slot: slot["start"])

        if required_input_energy_kwh >= total_possible_energy_kwh:
            return round(float(user_input_limit_w), 4)

        remaining_energy_kwh = required_input_energy_kwh
        allocations: dict[datetime, float] = {
            slot["start"]: 0.0 for slot in remaining_slots
        }

        sorted_slots = sorted(
            remaining_slots,
            key=lambda slot: (float(slot["price"]), -slot["start"].timestamp()),
        )

        for slot in sorted_slots:
            if remaining_energy_kwh <= 0.0:
                break
            slot_energy = min(float(slot["max_energy_kwh"]), remaining_energy_kwh)
            allocations[slot["start"]] = slot_energy
            remaining_energy_kwh -= slot_energy

        current_start = current_slot["start"]
        current_duration_hours = float(current_slot["duration_hours"])
        current_allocated_energy_kwh = allocations.get(current_start, 0.0)
        if current_duration_hours <= 0.0 or current_allocated_energy_kwh <= 0.0:
            return 0.0

        charge_power_w = (current_allocated_energy_kwh / current_duration_hours) * 1000.0
        return min(round(charge_power_w, 4), round(float(user_input_limit_w), 4))

    def get_active_grid_import_sensor_entity_id(self) -> str | None:
        """Return the currently active import source entity ID."""
        active = self._get_latest_updated_power_source(self.get_grid_import_sensor_entity_ids())
        return active[0] if active else None

    def get_active_grid_export_sensor_entity_id(self) -> str | None:
        """Return the currently active export source entity ID."""
        active = self._get_latest_updated_power_source(self.get_grid_export_sensor_entity_ids())
        return active[0] if active else None

    def get_soc_min_sensor_entity_id(self) -> str | None:
        """Return the configured minimum SoC sensor."""
        value = self.config_entry.options.get(
            CONF_SOC_MIN_SENSOR,
            self.config_entry.data.get(CONF_SOC_MIN_SENSOR),
        )
        return str(value) if value else None

    def get_soc_max_sensor_entity_id(self) -> str | None:
        """Return the configured maximum SoC sensor."""
        value = self.config_entry.options.get(
            CONF_SOC_MAX_SENSOR,
            self.config_entry.data.get(CONF_SOC_MAX_SENSOR),
        )
        return str(value) if value else None

    def get_soc_current_sensor_entity_id(self) -> str | None:
        """Return the configured current SoC sensor."""
        value = self.config_entry.options.get(
            CONF_SOC_CURRENT_SENSOR,
            self.config_entry.data.get(CONF_SOC_CURRENT_SENSOR),
        )
        return str(value) if value else None

    def get_current_price(self, home_key: str) -> float | None:
        """Return the current active price for a home."""
        rows = self.data.get(home_key, [])
        parsed = self._parse_rows(rows)
        current_index = self._get_current_index(parsed)
        if current_index is None:
            return None
        return parsed[current_index][1]

    def is_current_favorable(self, home_key: str) -> bool:
        """Return whether the current slot is favorable within today's threshold."""
        block = self._get_selected_favorable_block(home_key)
        if not block:
            return False

        parsed = self._parse_rows(self.data.get(home_key, []))
        now = dt_util.now()
        block_start = block[0][0]
        block_end = self._get_block_end(block, parsed)
        if block_end is None:
            return False
        return block_start <= now < block_end

    def get_current_favorable_phase_id(self, home_key: str) -> str | None:
        """Return a stable identifier for the currently active favorable phase."""
        if not self.is_current_favorable(home_key):
            return None
        phase_rows = self.get_favorable_phase_rows(home_key)
        if not phase_rows:
            return None
        phase_start = phase_rows[0][0]
        phase_end = self.get_favorable_phase_end(home_key)
        if phase_end is None:
            return None
        return f"{home_key}|{self._isoformat(phase_start)}|{self._isoformat(phase_end)}"

    def get_favorable_phase_start(self, home_key: str) -> datetime | None:
        """Return the start of the selected favorable block."""
        phase_rows = self.get_favorable_phase_rows(home_key)
        if not phase_rows:
            return None
        return phase_rows[0][0]

    def get_favorable_phase_end(self, home_key: str) -> datetime | None:
        """Return the end of the selected favorable block."""
        parsed = self._parse_rows(self.data.get(home_key, []))
        return self._get_block_end(self.get_favorable_phase_rows(home_key), parsed)

    def get_favorable_phase_rows(self, home_key: str) -> list[tuple[datetime, float]]:
        """Return the currently relevant favorable block.

        The threshold is calculated per day using that day's minimum and maximum price.
        The integration first searches within today's data. Only when no current or upcoming
        favorable phase exists for today will it fall back to tomorrow. If today's favorable
        phase has already passed, no later one exists today, and tomorrow is still unavailable,
        the most recent favorable phase from today is returned.
        """
        return self._get_selected_favorable_block(home_key)

    def get_price_attributes(self, home_key: str) -> OrderedDict[str, Any]:
        """Build the ordered sensor attributes for a home."""
        rows = self.data.get(home_key, [])
        parsed = self._parse_rows(rows)

        today = dt_util.now().date()
        tomorrow = today + timedelta(days=1)

        today_rows = [(dt_value, price) for dt_value, price in parsed if dt_value.date() == today]
        tomorrow_rows = [
            (dt_value, price) for dt_value, price in parsed if dt_value.date() == tomorrow
        ]
        overall_rows = parsed

        attributes: OrderedDict[str, Any] = OrderedDict()

        self._append_stats(attributes, "today", today_rows)
        self._append_stats(attributes, "tomorrow", tomorrow_rows)
        self._append_stats(attributes, "overall", overall_rows)
        attributes[ATTR_DATA] = rows

        return attributes

    def get_favorable_phase_attributes(self, home_key: str) -> OrderedDict[str, Any]:
        """Build the ordered attributes for the selected favorable block."""
        phase_rows = self.get_favorable_phase_rows(home_key)
        end = self.get_favorable_phase_end(home_key)
        phase_thresholds = self._get_threshold_metadata_for_phase(home_key, phase_rows)

        attributes: OrderedDict[str, Any] = OrderedDict()
        attributes[ATTR_FAVORABLE_FROM] = self._isoformat(phase_rows[0][0]) if phase_rows else None
        attributes[ATTR_FAVORABLE_UNTIL] = self._isoformat(end) if end else None
        attributes[ATTR_THRESHOLD_MIN_PRICE] = phase_thresholds.get("min_price")
        attributes[ATTR_THRESHOLD_MAX_PRICE] = phase_thresholds.get("threshold_price")
        self._append_stats(attributes, "favorable_phase", phase_rows)
        attributes[ATTR_DATA] = [
            {"start_time": self._isoformat(start), "price_per_kwh": price}
            for start, price in phase_rows
        ]
        return attributes

    def get_grid_power_balance_value(self) -> float | None:
        """Return the current grid power balance in watts."""
        if self._grid_power_stats.get("date") != dt_util.now().date().isoformat():
            current = self._calculate_current_grid_power_watts()
            return round(current, 4) if current is not None else None

        value = self._grid_power_stats.get("last_value")
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            current = self._calculate_current_grid_power_watts()
            return round(current, 4) if current is not None else None

    def get_grid_power_balance_attributes(self) -> OrderedDict[str, Any]:
        """Return current-day grid power balance statistics."""
        attributes: OrderedDict[str, Any] = OrderedDict()

        import_value = self.get_grid_import_value()
        attributes[ATTR_GRID_IMPORT] = self._round_or_none(import_value)

        if self.get_grid_export_sensor_entity_ids():
            attributes[ATTR_GRID_EXPORT] = self._round_or_none(self.get_grid_export_value())

        today_str = dt_util.now().date().isoformat()
        if self._grid_power_stats.get("date") != today_str:
            attributes["min_today_value"] = None
            attributes["min_today_time"] = None
            attributes["max_today_value"] = None
            attributes["max_today_time"] = None
            attributes["avg_today_value"] = None
            return attributes

        attributes["min_today_value"] = self._round_or_none(self._grid_power_stats.get("min_value"))
        attributes["min_today_time"] = self._grid_power_stats.get("min_time")
        attributes["max_today_value"] = self._round_or_none(self._grid_power_stats.get("max_value"))
        attributes["max_today_time"] = self._grid_power_stats.get("max_time")
        sum_value = self._grid_power_stats.get("sum_value")
        count_value = self._grid_power_stats.get("count")
        avg_value = None
        try:
            if float(count_value) > 0:
                avg_value = float(sum_value) / float(count_value)
        except (TypeError, ValueError, ZeroDivisionError):
            avg_value = None
        attributes["avg_today_value"] = self._round_or_none(avg_value)
        return attributes

    def get_grid_import_value(self) -> float | None:
        """Return the active grid import sensor value in watts."""
        active = self._get_latest_updated_power_source(self.get_grid_import_sensor_entity_ids())
        return self._round_or_none(active[1]) if active else None

    def get_grid_export_value(self) -> float | None:
        """Return the active grid export sensor value in watts."""
        active = self._get_latest_updated_power_source(self.get_grid_export_sensor_entity_ids())
        return self._round_or_none(active[1]) if active else None

    def get_current_soc(self) -> int | None:
        """Return the current state of charge percentage as a whole number."""
        entity_id = self.get_soc_current_sensor_entity_id()
        value = self._get_percentage_from_entity(entity_id)
        return int(round(value)) if value is not None else None

    def get_min_soc(self) -> int | None:
        """Return the configured minimum state of charge percentage as a whole number."""
        entity_id = self.get_soc_min_sensor_entity_id()
        value = self._get_percentage_from_entity(entity_id)
        return int(round(value)) if value is not None else None

    def get_max_soc(self) -> int | None:
        """Return the configured maximum state of charge percentage as a whole number."""
        entity_id = self.get_soc_max_sensor_entity_id()
        value = self._get_percentage_from_entity(entity_id)
        return int(round(value)) if value is not None else None

    def get_state_of_charge_attributes(self) -> OrderedDict[str, Any]:
        """Return attributes for the combined SoC sensor."""
        attributes: OrderedDict[str, Any] = OrderedDict()
        attributes[ATTR_MINIMUM_SOC] = self.get_min_soc()
        attributes[ATTR_MAXIMUM_SOC] = self.get_max_soc()
        return attributes

    def get_battery_capacity_attributes(self) -> OrderedDict[str, Any]:
        """Return derived energy attributes for the configured battery capacity."""
        attributes: OrderedDict[str, Any] = OrderedDict()
        attributes[ATTR_CURRENT_ENERGY] = self._calculate_energy_from_soc(self.get_current_soc())
        attributes[ATTR_ENERGY_AT_MINIMUM_SOC] = self._calculate_energy_from_soc(self.get_min_soc())
        attributes[ATTR_ENERGY_AT_MAXIMUM_SOC] = self._calculate_energy_from_soc(self.get_max_soc())
        return attributes

    def _append_stats(
        self,
        attributes: OrderedDict[str, Any],
        scope: str,
        rows: list[tuple[datetime, float]],
    ) -> None:
        """Append ordered min/avg/max price and time attributes."""
        minimum = self._stat_min(rows)
        average = self._stat_avg(rows)
        maximum = self._stat_max(rows)

        attributes[f"min_{scope}_price"] = minimum[1] if minimum else None
        attributes[f"avg_{scope}_price"] = average[1] if average else None
        attributes[f"max_{scope}_price"] = maximum[1] if maximum else None
        attributes[f"min_{scope}_time"] = self._isoformat(minimum[0]) if minimum else None
        attributes[f"avg_{scope}_time"] = self._isoformat(average[0]) if average else None
        attributes[f"max_{scope}_time"] = self._isoformat(maximum[0]) if maximum else None

    def _stat_min(self, rows: list[tuple[datetime, float]]) -> tuple[datetime, float] | None:
        if not rows:
            return None
        return min(rows, key=lambda item: (item[1], item[0]))

    def _stat_max(self, rows: list[tuple[datetime, float]]) -> tuple[datetime, float] | None:
        if not rows:
            return None
        return max(rows, key=lambda item: (item[1], -item[0].timestamp()))

    def _stat_avg(self, rows: list[tuple[datetime, float]]) -> tuple[datetime, float] | None:
        if not rows:
            return None
        avg_price = round(mean(price for _, price in rows), 4)
        closest = min(rows, key=lambda item: (abs(item[1] - avg_price), item[0]))
        return (closest[0], avg_price)

    def _parse_rows(self, rows: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
        parsed: list[tuple[datetime, float]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            dt_value = dt_util.parse_datetime(str(row.get("start_time")))
            price = row.get("price_per_kwh")
            if dt_value is None:
                continue
            try:
                parsed.append((dt_util.as_local(dt_value), round(float(price), 4)))
            except (TypeError, ValueError):
                continue
        parsed.sort(key=lambda item: item[0])
        return parsed

    def _normalize_price_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            raw_time = row.get("start_time")
            raw_price = row.get("price")
            dt_value = dt_util.parse_datetime(str(raw_time))
            if dt_value is None:
                continue

            try:
                price = round(float(raw_price), 4)
            except (TypeError, ValueError):
                continue

            local_dt = dt_util.as_local(dt_value)
            normalized.append(
                {
                    "start_time": self._isoformat(local_dt),
                    "price_per_kwh": price,
                }
            )

        normalized.sort(key=lambda item: item["start_time"])
        return normalized

    def _get_current_index(self, parsed: list[tuple[datetime, float]]) -> int | None:
        """Return the index of the active slot."""
        if not parsed:
            return None

        now = dt_util.now()
        for index, (start, _) in enumerate(parsed):
            if index + 1 < len(parsed):
                next_start = parsed[index + 1][0]
            else:
                next_start = start + timedelta(minutes=15)

            if start <= now < next_start:
                return index

        if now < parsed[0][0]:
            return 0

        return len(parsed) - 1

    def _get_selected_favorable_block(self, home_key: str) -> list[tuple[datetime, float]]:
        """Return the relevant favorable block using today's threshold first and tomorrow only as fallback."""
        parsed = self._parse_rows(self.data.get(home_key, []))
        if not parsed:
            return []

        now = dt_util.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        today_blocks = self._get_favorable_blocks_for_day(home_key, parsed, today)
        current_today = self._find_current_block(today_blocks, parsed, now)
        if current_today:
            return current_today

        next_today = self._find_next_block(today_blocks, parsed, now)
        if next_today:
            return next_today

        tomorrow_blocks = self._get_favorable_blocks_for_day(home_key, parsed, tomorrow)
        if tomorrow_blocks:
            return tomorrow_blocks[0]

        last_today = self._find_most_recent_block(today_blocks, parsed, now)
        if last_today:
            return last_today

        return []

    def _get_favorable_blocks_for_day(
        self,
        home_key: str,
        parsed: list[tuple[datetime, float]],
        target_day,
    ) -> list[list[tuple[datetime, float]]]:
        """Return all favorable contiguous blocks for a given local day."""
        day_items = [
            (index, item)
            for index, item in enumerate(parsed)
            if item[0].date() == target_day
        ]
        if not day_items:
            return []

        day_prices = [item for _, item in day_items]
        min_price, threshold_price = self._get_day_price_threshold(home_key, day_prices)
        if min_price is None or threshold_price is None:
            return []

        favorable_indices = [
            index
            for index, (_, price) in day_items
            if self._is_price_within_threshold(price, threshold_price)
        ]
        if not favorable_indices:
            return []

        blocks: list[list[tuple[datetime, float]]] = []
        current_block_indices: list[int] = []
        for index in favorable_indices:
            if not current_block_indices or index == current_block_indices[-1] + 1:
                current_block_indices.append(index)
            else:
                blocks.append([parsed[i] for i in current_block_indices])
                current_block_indices = [index]

        if current_block_indices:
            blocks.append([parsed[i] for i in current_block_indices])

        return blocks

    def _get_day_price_threshold(
        self,
        home_key: str,
        day_rows: list[tuple[datetime, float]],
    ) -> tuple[float | None, float | None]:
        """Return the day's minimum price and maximum favorable price based on min/max span."""
        if not day_rows:
            return (None, None)

        min_price = min(price for _, price in day_rows)
        max_price = max(price for _, price in day_rows)
        threshold_percent = self.get_threshold_for_home(home_key)
        threshold_percent = max(0.0, min(100.0, float(threshold_percent)))

        min_decimal = self._round_price_half_up(min_price)
        max_decimal = self._round_price_half_up(max_price)
        percent_decimal = Decimal(str(threshold_percent))
        threshold_price = min_decimal + ((max_decimal - min_decimal) * percent_decimal / Decimal("100"))
        threshold_decimal = threshold_price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return (float(min_decimal), float(threshold_decimal))

    @staticmethod
    def _round_price_half_up(value: float) -> Decimal:
        """Round a price mathematically to 4 decimal places."""
        return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def _is_price_within_threshold(self, price: float, threshold_price: float) -> bool:
        """Return whether a price is at or below the rounded threshold price."""
        return self._round_price_half_up(price) <= self._round_price_half_up(threshold_price)

    def _get_threshold_metadata_for_phase(
        self,
        home_key: str,
        phase_rows: list[tuple[datetime, float]],
    ) -> dict[str, float | None]:
        """Return threshold metadata for the day the selected phase belongs to."""
        if not phase_rows:
            return {"min_price": None, "threshold_price": None}

        target_day = phase_rows[0][0].date()
        parsed = self._parse_rows(self.data.get(home_key, []))
        day_rows = [item for item in parsed if item[0].date() == target_day]
        min_price, threshold_price = self._get_day_price_threshold(home_key, day_rows)
        return {"min_price": min_price, "threshold_price": threshold_price}

    def _find_current_block(
        self,
        blocks: list[list[tuple[datetime, float]]],
        parsed: list[tuple[datetime, float]],
        now: datetime,
    ) -> list[tuple[datetime, float]] | None:
        """Return the block the current time is inside of, if any."""
        for block in blocks:
            block_start = block[0][0]
            block_end = self._get_block_end(block, parsed)
            if block_end is not None and block_start <= now < block_end:
                return block
        return None

    def _find_next_block(
        self,
        blocks: list[list[tuple[datetime, float]]],
        parsed: list[tuple[datetime, float]],
        now: datetime,
    ) -> list[tuple[datetime, float]] | None:
        """Return the next future favorable block."""
        for block in blocks:
            block_end = self._get_block_end(block, parsed)
            if block_end is None:
                continue
            if block_end <= now:
                continue
            if block[0][0] >= now:
                return block
        return None

    def _find_most_recent_block(
        self,
        blocks: list[list[tuple[datetime, float]]],
        parsed: list[tuple[datetime, float]],
        now: datetime,
    ) -> list[tuple[datetime, float]] | None:
        """Return the most recent past block for the day."""
        latest_block: list[tuple[datetime, float]] | None = None
        latest_end: datetime | None = None
        for block in blocks:
            block_end = self._get_block_end(block, parsed)
            if block_end is None or block_end > now:
                continue
            if latest_end is None or block_end > latest_end:
                latest_block = block
                latest_end = block_end
        return latest_block

    def _get_block_end(
        self,
        block: list[tuple[datetime, float]],
        parsed: list[tuple[datetime, float]] | None = None,
    ) -> datetime | None:
        """Return the end datetime of a favorable block."""
        if not block:
            return None
        last_start = block[-1][0]
        if parsed:
            for index, (start, _) in enumerate(parsed):
                if start != last_start:
                    continue
                if (index + 1) < len(parsed):
                    return parsed[index + 1][0]
                return parsed[index][0] + timedelta(minutes=15)
        return last_start + timedelta(minutes=15)

    def _calculate_current_grid_power_watts(self) -> float | None:
        """Calculate the signed grid power balance in watts."""
        import_active = self._get_latest_updated_power_source(self.get_grid_import_sensor_entity_ids())
        if not import_active:
            return None
        import_watts = import_active[1]

        export_active = self._get_latest_updated_power_source(self.get_grid_export_sensor_entity_ids())
        if not export_active:
            return round(import_watts, 4)

        export_watts = export_active[1]
        return round(import_watts - export_watts, 4)

    def _get_latest_updated_power_source(
        self,
        entity_ids: list[str],
    ) -> tuple[str, float] | None:
        """Return the valid power source that was updated most recently."""
        latest: tuple[str, float, datetime] | None = None
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            watts = state_to_watts(state)
            if state is None or watts is None:
                continue
            updated = state.last_updated or state.last_changed or dt_util.now()
            if latest is None or updated > latest[2]:
                latest = (entity_id, watts, updated)

        if latest is None:
            return None
        return (latest[0], round(latest[1], 4))

    def _get_percentage_from_entity(self, entity_id: str | None) -> float | None:
        """Return a percentage value from an entity state."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return state_to_percentage(state)

    def _calculate_energy_from_soc(self, soc_value: float | None) -> float | None:
        """Calculate energy content in kWh for a given SoC percentage."""
        if soc_value is None:
            return None
        return round(self.get_battery_capacity_kwh() * float(soc_value) / 100.0, 4)

    def _create_new_grid_stats(
        self,
        day: str,
        value: float,
        now: datetime,
    ) -> dict[str, Any]:
        """Create a new current-day grid statistics structure."""
        iso_now = self._isoformat(now)
        value = round(float(value), 4)
        return {
            "date": day,
            "last_value": value,
            "min_value": value,
            "min_time": iso_now,
            "max_value": value,
            "max_time": iso_now,
            "sum_value": value,
            "count": 1,
        }

    def _update_grid_stats(self, value: float, now: datetime) -> None:
        """Update the stored current-day grid statistics."""
        value = round(float(value), 4)
        iso_now = self._isoformat(now)
        self._grid_power_stats["last_value"] = value

        try:
            current_min = float(self._grid_power_stats.get("min_value"))
        except (TypeError, ValueError):
            current_min = value
        if value < current_min:
            self._grid_power_stats["min_value"] = value
            self._grid_power_stats["min_time"] = iso_now
        elif "min_value" not in self._grid_power_stats:
            self._grid_power_stats["min_value"] = value
            self._grid_power_stats["min_time"] = iso_now

        try:
            current_max = float(self._grid_power_stats.get("max_value"))
        except (TypeError, ValueError):
            current_max = value
        if value > current_max:
            self._grid_power_stats["max_value"] = value
            self._grid_power_stats["max_time"] = iso_now
        elif "max_value" not in self._grid_power_stats:
            self._grid_power_stats["max_value"] = value
            self._grid_power_stats["max_time"] = iso_now

        try:
            self._grid_power_stats["sum_value"] = round(
                float(self._grid_power_stats.get("sum_value", 0.0)) + value,
                4,
            )
        except (TypeError, ValueError):
            self._grid_power_stats["sum_value"] = value

        try:
            self._grid_power_stats["count"] = int(self._grid_power_stats.get("count", 0)) + 1
        except (TypeError, ValueError):
            self._grid_power_stats["count"] = 1

    def _isoformat(self, dt_value: datetime | None) -> str | None:
        """Return ISO formatted local datetime with milliseconds."""
        if dt_value is None:
            return None
        local = dt_util.as_local(dt_value)
        return local.isoformat(timespec="milliseconds")

    def _round_or_none(self, value: Any) -> float | None:
        """Return a rounded float or None."""
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None
