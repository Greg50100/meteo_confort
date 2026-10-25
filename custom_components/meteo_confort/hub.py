"""Hub: reads source sensors, runs the calculations and notifies entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .calculations import PROFILE_INDOOR, Measurements, RollingMean, Settings, compute_all
from .const import (
    CONF_CO2,
    CONF_HUMIDITY,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_PRESSURE,
    CONF_PROFILE,
    CONF_RADIANT_TEMPERATURE,
    CONF_TEMPERATURE,
    CONF_WIND_SPEED,
    DOMAIN,
    MANUFACTURER,
    SOURCE_KEYS,
)

_LOGGER = logging.getLogger(__name__)

_SETTING_FIELDS = {f.name for f in fields(Settings)}

STORAGE_VERSION = 1
SAVE_DELAY = 60  # seconds
# Recompute regularly so time-based values (mold mean) move on even when the
# source sensors do not change
REFRESH_INTERVAL = timedelta(minutes=5)


def storage_key(entry_id: str) -> str:
    """Storage file holding the history of an entry."""
    return f"{DOMAIN}.{entry_id}"


class MeteoConfortHub:
    """Holds the latest computed values for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.profile: str = entry.data[CONF_PROFILE]
        self.options: dict[str, Any] = dict(entry.options)
        self.data: dict[str, Any] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=self.profile,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, storage_key(entry.entry_id))
        self._mold_history = (
            RollingMean(self.settings.mold_window * 3600) if self.profile == PROFILE_INDOOR else None
        )

    async def async_load(self) -> None:
        """Restore the mold humidity history saved before a restart."""
        if self._mold_history is None:
            return
        if (stored := await self._store.async_load()) and (samples := stored.get("mold_samples")):
            self._mold_history.samples.extend((float(ts), float(value)) for ts, value in samples)

    async def async_save(self) -> None:
        """Write the history now (on unload)."""
        if self._mold_history is not None:
            await self._store.async_save(self._data_to_save())

    def _data_to_save(self) -> dict[str, Any]:
        samples = self._mold_history.samples if self._mold_history is not None else []
        return {"mold_samples": [list(sample) for sample in samples]}

    @property
    def sources(self) -> dict[str, str]:
        """Configured source entity ids keyed by role."""
        return {key: self.options[key] for key in SOURCE_KEYS if self.options.get(key)}

    def has_input(self, key: str) -> bool:
        """Return True if the given source sensor is configured."""
        return bool(self.options.get(key))

    @property
    def settings(self) -> Settings:
        """Settings built from the entry options."""
        values = {k: v for k, v in self.options.items() if k in _SETTING_FIELDS}
        values.setdefault("altitude", self.hass.config.elevation or 0)
        return Settings(**values)

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Register an entity update callback."""
        self._listeners.append(update_callback)

        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Compute once and start tracking the source sensors."""
        self._recompute()
        unsubscribers = [
            async_track_state_change_event(
                self.hass, list(self.sources.values()), self._handle_update
            ),
            async_track_time_interval(self.hass, self._handle_update, REFRESH_INTERVAL),
        ]

        @callback
        def stop() -> None:
            for unsubscribe in unsubscribers:
                unsubscribe()

        return stop

    @callback
    def _handle_update(self, *_: Any) -> None:
        self._recompute()
        for update_callback in list(self._listeners):
            update_callback()

    @callback
    def _recompute(self) -> None:
        measurements = Measurements(
            temperature=self._read_temperature(CONF_TEMPERATURE),
            humidity=self._read(CONF_HUMIDITY)[0],
            pressure=self._read_pressure(CONF_PRESSURE),
            wind_speed=self._read_speed(CONF_WIND_SPEED),
            co2=self._read(CONF_CO2)[0],
            radiant_temperature=self._read_temperature(CONF_RADIANT_TEMPERATURE),
            outdoor_temperature=self._read_temperature(CONF_OUTDOOR_TEMPERATURE),
            outdoor_humidity=self._read(CONF_OUTDOOR_HUMIDITY)[0],
        )
        try:
            self.data = compute_all(
                self.profile,
                measurements,
                self.settings,
                previous=self.data,
                now=dt_util.utcnow().timestamp(),
                mold_history=self._mold_history,
            )
        except (ValueError, ZeroDivisionError, OverflowError) as err:
            _LOGGER.warning("%s: calculation failed (%s): %s", self.entry.title, err, measurements)
            self.data = {}
        if self._mold_history is not None:
            self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    def _read(self, key: str) -> tuple[float | None, str | None]:
        entity_id = self.options.get(key)
        if not entity_id:
            return None, None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None, None
        try:
            value = float(state.state)
        except ValueError:
            _LOGGER.debug("%s has a non numeric state: %s", entity_id, state.state)
            return None, None
        return value, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    def _read_converted(self, key: str, converter: Any, target: str) -> float | None:
        value, unit = self._read(key)
        if value is None or not unit or unit == target:
            return value
        try:
            return converter.convert(value, unit, target)
        except HomeAssistantError:
            _LOGGER.debug("Unsupported unit %s for %s, assuming %s", unit, key, target)
            return value

    def _read_temperature(self, key: str) -> float | None:
        return self._read_converted(key, TemperatureConverter, UnitOfTemperature.CELSIUS)

    def _read_pressure(self, key: str) -> float | None:
        return self._read_converted(key, PressureConverter, UnitOfPressure.HPA)

    def _read_speed(self, key: str) -> float | None:
        return self._read_converted(key, SpeedConverter, UnitOfSpeed.KILOMETERS_PER_HOUR)
