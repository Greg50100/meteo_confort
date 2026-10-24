"""Config and options flows for Météo & Confort."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME, PERCENTAGE, UnitOfLength, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .calculations import PRESSURE_SEA_LEVEL, PRESSURE_STATION, PROFILE_INDOOR, PROFILE_OUTDOOR
from .const import (
    CONF_AIR_SPEED,
    CONF_ALTITUDE,
    CONF_CLO,
    CONF_CO2,
    CONF_CO2_MAX,
    CONF_FRSI,
    CONF_HUMIDITY,
    CONF_HUMIDITY_MAX,
    CONF_HUMIDITY_MIN,
    CONF_MET,
    CONF_MOLD_THRESHOLD,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_PRESSURE,
    CONF_PRESSURE_TYPE,
    CONF_PROFILE,
    CONF_RADIANT_TEMPERATURE,
    CONF_TEMP_MAX,
    CONF_TEMP_MIN,
    CONF_TEMPERATURE,
    CONF_WIND_SPEED,
    DEFAULTS,
    DOMAIN,
    SECTION_SETTINGS,
)

_TEMPERATURE = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.TEMPERATURE)
)
_HUMIDITY = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.HUMIDITY)
)
_PRESSURE = EntitySelector(
    EntitySelectorConfig(
        domain="sensor",
        device_class=[SensorDeviceClass.PRESSURE, SensorDeviceClass.ATMOSPHERIC_PRESSURE],
    )
)
_WIND = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.WIND_SPEED)
)
_CO2 = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.CO2)
)


def _number(minimum: float, maximum: float, step: float, unit: str | None = None) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement=unit, mode=NumberSelectorMode.BOX
        )
    )


def _entity(key: str, required: bool, values: dict[str, Any]) -> vol.Marker:
    marker = vol.Required if required else vol.Optional
    return marker(key, description={"suggested_value": values.get(key)})


def _setting(key: str, values: dict[str, Any], default: Any) -> vol.Required:
    return vol.Required(key, default=values.get(key, default))


def _build_schema(
    profile: str, values: dict[str, Any], altitude: float, with_name: bool
) -> vol.Schema:
    schema: dict[Any, Any] = {}
    if with_name:
        schema[vol.Required(CONF_NAME, default=values.get(CONF_NAME, ""))] = TextSelector()
    schema[_entity(CONF_TEMPERATURE, True, values)] = _TEMPERATURE
    schema[_entity(CONF_HUMIDITY, True, values)] = _HUMIDITY

    settings: dict[Any, Any] = {}
    if profile == PROFILE_OUTDOOR:
        schema[_entity(CONF_PRESSURE, False, values)] = _PRESSURE
        schema[_entity(CONF_WIND_SPEED, False, values)] = _WIND
        settings[_setting(CONF_ALTITUDE, values, altitude)] = _number(-500, 9000, 1, UnitOfLength.METERS)
        settings[_setting(CONF_PRESSURE_TYPE, values, DEFAULTS.pressure_type)] = SelectSelector(
            SelectSelectorConfig(
                options=[PRESSURE_STATION, PRESSURE_SEA_LEVEL],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_PRESSURE_TYPE,
            )
        )
    else:
        schema[_entity(CONF_CO2, False, values)] = _CO2
        schema[_entity(CONF_RADIANT_TEMPERATURE, False, values)] = _TEMPERATURE
        schema[_entity(CONF_OUTDOOR_TEMPERATURE, False, values)] = _TEMPERATURE
        schema[_entity(CONF_OUTDOOR_HUMIDITY, False, values)] = _HUMIDITY
        celsius = UnitOfTemperature.CELSIUS
        settings.update(
            {
                _setting(CONF_TEMP_MIN, values, DEFAULTS.temp_min): _number(5, 35, 0.5, celsius),
                _setting(CONF_TEMP_MAX, values, DEFAULTS.temp_max): _number(5, 35, 0.5, celsius),
                _setting(CONF_HUMIDITY_MIN, values, DEFAULTS.humidity_min): _number(0, 100, 1, PERCENTAGE),
                _setting(CONF_HUMIDITY_MAX, values, DEFAULTS.humidity_max): _number(0, 100, 1, PERCENTAGE),
                _setting(CONF_CO2_MAX, values, DEFAULTS.co2_max): _number(400, 5000, 50, "ppm"),
                _setting(CONF_MET, values, DEFAULTS.met): _number(0.7, 4, 0.1, "met"),
                _setting(CONF_CLO, values, DEFAULTS.clo): _number(0, 2, 0.05, "clo"),
                _setting(CONF_AIR_SPEED, values, DEFAULTS.air_speed): _number(
                    0, 2, 0.05, UnitOfSpeed.METERS_PER_SECOND
                ),
                _setting(CONF_FRSI, values, DEFAULTS.frsi): _number(0.3, 1, 0.01),
                _setting(CONF_MOLD_THRESHOLD, values, DEFAULTS.mold_threshold): _number(
                    50, 100, 1, PERCENTAGE
                ),
            }
        )

    schema[vol.Required(SECTION_SETTINGS)] = section(vol.Schema(settings), {"collapsed": True})
    return vol.Schema(schema)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    data = {k: v for k, v in user_input.items() if k != SECTION_SETTINGS and v}
    data.update(user_input.get(SECTION_SETTINGS, {}))
    return data


def _validate(profile: str, data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data[CONF_TEMPERATURE] == data.get(CONF_OUTDOOR_TEMPERATURE):
        errors[CONF_OUTDOOR_TEMPERATURE] = "same_entity"
    if data[CONF_HUMIDITY] == data.get(CONF_OUTDOOR_HUMIDITY):
        errors[CONF_OUTDOOR_HUMIDITY] = "same_entity"
    if profile == PROFILE_INDOOR:
        if data[CONF_TEMP_MIN] >= data[CONF_TEMP_MAX]:
            errors["base"] = "invalid_temperature_range"
        elif data[CONF_HUMIDITY_MIN] >= data[CONF_HUMIDITY_MAX]:
            errors["base"] = "invalid_humidity_range"
    return errors


class MeteoConfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a new outdoor or indoor profile."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user pick the profile type."""
        return self.async_show_menu(step_id="user", menu_options=[PROFILE_OUTDOOR, PROFILE_INDOOR])

    async def async_step_outdoor(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Outdoor weather station profile."""
        return await self._async_step_profile(PROFILE_OUTDOOR, user_input)

    async def async_step_indoor(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Indoor room profile."""
        return await self._async_step_profile(PROFILE_INDOOR, user_input)

    async def _async_step_profile(
        self, profile: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        values: dict[str, Any] = {}
        if user_input is not None:
            values = _flatten(user_input)
            errors = _validate(profile, values)
            if not errors:
                await self.async_set_unique_id(
                    f"{profile}_{values[CONF_TEMPERATURE]}_{values[CONF_HUMIDITY]}"
                )
                self._abort_if_unique_id_configured()
                title = values.pop(CONF_NAME, None) or profile.capitalize()
                return self.async_create_entry(
                    title=title, data={CONF_PROFILE: profile}, options=values
                )

        return self.async_show_form(
            step_id=profile,
            data_schema=_build_schema(
                profile, values, self.hass.config.elevation or 0, with_name=True
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return MeteoConfortOptionsFlow()


class MeteoConfortOptionsFlow(OptionsFlow):
    """Change source sensors and parameters of an existing profile."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single options step."""
        profile = self.config_entry.data[CONF_PROFILE]
        errors: dict[str, str] = {}
        values = dict(self.config_entry.options)
        if user_input is not None:
            values = _flatten(user_input)
            errors = _validate(profile, values)
            if not errors:
                return self.async_create_entry(data=values)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(
                profile, values, self.hass.config.elevation or 0, with_name=False
            ),
            errors=errors,
        )
