"""Sensor platform for Météo & Confort."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MeteoConfortConfigEntry
from .calculations import (
    CO2_LEVELS,
    COMFORT_LEVELS,
    DEW_POINT_PERCEPTIONS,
    HEAT_STRESS_LEVELS,
    MOLD_RISKS,
    PRESSURE_SEA_LEVEL,
    PRESSURE_STATION,
    PROFILE_INDOOR,
    PROFILE_OUTDOOR,
    THERMAL_SENSATIONS,
    WIND_CHILL_RISKS,
)
from .const import (
    CONF_CO2,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_PRESSURE,
    CONF_PRESSURE_TYPE,
    CONF_WIND_SPEED,
)
from .entity import MeteoConfortEntity, MeteoConfortEntityDescription, is_supported

OUTDOOR = (PROFILE_OUTDOOR,)
INDOOR = (PROFILE_INDOOR,)


@dataclass(frozen=True, kw_only=True)
class MeteoConfortSensorDescription(SensorEntityDescription, MeteoConfortEntityDescription):
    """Sensor description."""


def _temperature(key: str, **kwargs: Any) -> MeteoConfortSensorDescription:
    return MeteoConfortSensorDescription(
        key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        **kwargs,
    )


def _enum(key: str, options: list[str], **kwargs: Any) -> MeteoConfortSensorDescription:
    return MeteoConfortSensorDescription(
        key=key, device_class=SensorDeviceClass.ENUM, options=options, **kwargs
    )


def _pressure(key: str, **kwargs: Any) -> MeteoConfortSensorDescription:
    return MeteoConfortSensorDescription(
        key=key,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=1,
        **kwargs,
    )


SENSORS: tuple[MeteoConfortSensorDescription, ...] = (
    # Common moisture & felt temperature values
    _temperature("dew_point"),
    _temperature("frost_point"),
    _temperature("wet_bulb"),
    _temperature("heat_index"),
    _temperature("humidex"),
    _temperature("discomfort_index", entity_registry_enabled_default=False),
    MeteoConfortSensorDescription(
        key="absolute_humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    MeteoConfortSensorDescription(
        key="vapor_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    MeteoConfortSensorDescription(
        key="mixing_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g/kg",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    MeteoConfortSensorDescription(
        key="specific_humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g/kg",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    MeteoConfortSensorDescription(
        key="enthalpy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kJ/kg",
        suggested_display_precision=1,
    ),
    MeteoConfortSensorDescription(
        key="air_density",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kg/m³",
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _enum("dew_point_perception", DEW_POINT_PERCEPTIONS),
    # Outdoor
    _temperature("feels_like", profiles=OUTDOOR),
    _temperature("wind_chill", profiles=OUTDOOR, requires=(CONF_WIND_SPEED,)),
    _temperature("apparent_temperature", profiles=OUTDOOR, requires=(CONF_WIND_SPEED,)),
    _pressure(
        "sea_level_pressure",
        profiles=OUTDOOR,
        requires=(CONF_PRESSURE,),
        exists_fn=lambda o: o.get(CONF_PRESSURE_TYPE, PRESSURE_STATION) == PRESSURE_STATION,
    ),
    _pressure(
        "station_pressure",
        profiles=OUTDOOR,
        requires=(CONF_PRESSURE,),
        exists_fn=lambda o: o.get(CONF_PRESSURE_TYPE) == PRESSURE_SEA_LEVEL,
    ),
    MeteoConfortSensorDescription(
        key="cloud_base",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
        profiles=OUTDOOR,
    ),
    MeteoConfortSensorDescription(
        key="beaufort",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Bft",
        profiles=OUTDOOR,
        requires=(CONF_WIND_SPEED,),
    ),
    _enum("heat_stress", HEAT_STRESS_LEVELS, profiles=OUTDOOR),
    _enum("wind_chill_risk", WIND_CHILL_RISKS, profiles=OUTDOOR, requires=(CONF_WIND_SPEED,)),
    # Indoor
    _enum("comfort_level", COMFORT_LEVELS, profiles=INDOOR),
    MeteoConfortSensorDescription(
        key="comfort_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        profiles=INDOOR,
    ),
    MeteoConfortSensorDescription(
        key="pmv",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        profiles=INDOOR,
    ),
    MeteoConfortSensorDescription(
        key="ppd",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        profiles=INDOOR,
    ),
    _enum("thermal_sensation", THERMAL_SENSATIONS, profiles=INDOOR),
    _enum("co2_level", CO2_LEVELS, profiles=INDOOR, requires=(CONF_CO2,)),
    _temperature("surface_temperature", profiles=INDOOR, requires=(CONF_OUTDOOR_TEMPERATURE,)),
    MeteoConfortSensorDescription(
        key="surface_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        profiles=INDOOR,
        requires=(CONF_OUTDOOR_TEMPERATURE,),
    ),
    _enum("mold_risk", MOLD_RISKS, profiles=INDOOR),
    MeteoConfortSensorDescription(
        key="outdoor_absolute_humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
        profiles=INDOOR,
        requires=(CONF_OUTDOOR_TEMPERATURE, CONF_OUTDOOR_HUMIDITY),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoConfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    hub = entry.runtime_data
    async_add_entities(
        MeteoConfortSensor(hub, description)
        for description in SENSORS
        if is_supported(description, hub)
    )


class MeteoConfortSensor(MeteoConfortEntity, SensorEntity):
    """A computed sensor."""

    entity_description: MeteoConfortSensorDescription

    @property
    def native_value(self) -> Any:
        """Return the computed value."""
        return self.hub.data.get(self.entity_description.key)
