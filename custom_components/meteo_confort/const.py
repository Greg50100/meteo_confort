"""Constants for the Météo & Confort integration."""

from __future__ import annotations

from .calculations import PROFILE_INDOOR, PROFILE_OUTDOOR, Settings

DOMAIN = "meteo_confort"
MANUFACTURER = "Météo & Confort"

CONF_PROFILE = "profile"
PROFILES = [PROFILE_OUTDOOR, PROFILE_INDOOR]

# Source sensors
CONF_TEMPERATURE = "temperature"
CONF_HUMIDITY = "humidity"
CONF_PRESSURE = "pressure"
CONF_WIND_SPEED = "wind_speed"
CONF_CO2 = "co2"
CONF_RADIANT_TEMPERATURE = "radiant_temperature"
CONF_OUTDOOR_TEMPERATURE = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"

SOURCE_KEYS = [
    CONF_TEMPERATURE,
    CONF_HUMIDITY,
    CONF_PRESSURE,
    CONF_WIND_SPEED,
    CONF_CO2,
    CONF_RADIANT_TEMPERATURE,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_HUMIDITY,
]

# Settings (names match the Settings dataclass fields)
CONF_ALTITUDE = "altitude"
CONF_PRESSURE_TYPE = "pressure_type"
CONF_TEMP_MIN = "temp_min"
CONF_TEMP_MAX = "temp_max"
CONF_HUMIDITY_MIN = "humidity_min"
CONF_HUMIDITY_MAX = "humidity_max"
CONF_CO2_MAX = "co2_max"
CONF_MET = "met"
CONF_CLO = "clo"
CONF_AIR_SPEED = "air_speed"
CONF_FRSI = "frsi"
CONF_MOLD_THRESHOLD = "mold_threshold"

SECTION_SETTINGS = "settings"

DEFAULTS = Settings()
