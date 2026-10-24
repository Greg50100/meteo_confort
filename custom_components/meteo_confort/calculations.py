"""Pure meteorological and thermal comfort calculations.

This module has no Home Assistant dependency so it can be unit tested on its
own. All temperatures are in °C, pressures in hPa, wind speeds in km/h unless
stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

PROFILE_OUTDOOR = "outdoor"
PROFILE_INDOOR = "indoor"

PRESSURE_STATION = "station"
PRESSURE_SEA_LEVEL = "sea_level"

# Magnus coefficients (Alduchov & Eskridge, 1996)
_A_WATER, _B_WATER, _C_WATER = 6.1094, 17.625, 243.04
_A_ICE, _B_ICE, _C_ICE = 6.1121, 22.587, 273.86

R_DRY_AIR = 287.05  # J/(kg·K)
R_WATER_VAPOR = 461.5  # J/(kg·K)
STANDARD_PRESSURE = 1013.25  # hPa
KELVIN = 273.15

# Minimum absolute humidity difference (g/m³) for airing to actually dry a room
VENTILATION_HUMIDITY_MARGIN = 1.0
# Minimum outdoor/indoor temperature gap (°C) for free cooling by airing
VENTILATION_COOLING_MARGIN = 2.0

DEW_POINT_PERCEPTIONS = [
    "dry",
    "very_comfortable",
    "comfortable",
    "slightly_humid",
    "humid",
    "very_humid",
    "oppressive",
]
HEAT_STRESS_LEVELS = ["none", "caution", "extreme_caution", "danger", "extreme_danger"]
WIND_CHILL_RISKS = ["low", "moderate", "high", "very_high", "severe", "extreme"]
COMFORT_LEVELS = [
    "comfortable",
    "cold",
    "hot",
    "dry",
    "humid",
    "cold_dry",
    "cold_humid",
    "hot_dry",
    "hot_humid",
]
THERMAL_SENSATIONS = [
    "cold",
    "cool",
    "slightly_cool",
    "neutral",
    "slightly_warm",
    "warm",
    "hot",
]
CO2_LEVELS = ["excellent", "good", "fair", "poor", "bad"]
MOLD_RISKS = ["low", "moderate", "high", "very_high"]
VENTILATION_REASONS = ["co2", "humidity", "cooling"]

_BEAUFORT_LIMITS_MS = [0.5, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]


# ---------------------------------------------------------------------------
# Humidity / moisture
# ---------------------------------------------------------------------------


def saturation_vapor_pressure(temp: float, over_ice: bool = False) -> float:
    """Saturation vapour pressure in hPa (Magnus formula)."""
    if over_ice:
        return _A_ICE * math.exp(_B_ICE * temp / (temp + _C_ICE))
    return _A_WATER * math.exp(_B_WATER * temp / (temp + _C_WATER))


def vapor_pressure(temp: float, humidity: float) -> float:
    """Actual vapour pressure in hPa."""
    return humidity / 100 * saturation_vapor_pressure(temp)


def dew_point(temp: float, humidity: float) -> float:
    """Dew point in °C."""
    gamma = math.log(humidity / 100) + _B_WATER * temp / (_C_WATER + temp)
    return _C_WATER * gamma / (_B_WATER - gamma)


def frost_point(temp: float, humidity: float) -> float:
    """Frost point in °C (equals dew point when the dew point is above 0 °C)."""
    td = dew_point(temp, humidity)
    if td >= 0:
        return td
    gamma = math.log(vapor_pressure(temp, humidity) / _A_ICE)
    return _C_ICE * gamma / (_B_ICE - gamma)


def absolute_humidity(temp: float, humidity: float) -> float:
    """Absolute humidity in g/m³."""
    e_pa = vapor_pressure(temp, humidity) * 100
    return e_pa / (R_WATER_VAPOR * (temp + KELVIN)) * 1000


def mixing_ratio(temp: float, humidity: float, pressure: float) -> float:
    """Mixing ratio in g of water per kg of dry air."""
    e = vapor_pressure(temp, humidity)
    return 621.97 * e / (pressure - e)


def specific_humidity(temp: float, humidity: float, pressure: float) -> float:
    """Specific humidity in g of water per kg of moist air."""
    e = vapor_pressure(temp, humidity)
    return 621.97 * e / (pressure - 0.378 * e)


def enthalpy(temp: float, humidity: float, pressure: float) -> float:
    """Specific enthalpy of moist air in kJ/kg of dry air."""
    w = mixing_ratio(temp, humidity, pressure) / 1000
    return 1.006 * temp + w * (2501 + 1.86 * temp)


def wet_bulb_temperature(temp: float, humidity: float) -> float:
    """Wet-bulb temperature in °C (Stull, 2011)."""
    rh = humidity
    return (
        temp * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(temp + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


def air_density(temp: float, humidity: float, pressure: float) -> float:
    """Density of moist air in kg/m³."""
    e = vapor_pressure(temp, humidity) * 100
    p_dry = pressure * 100 - e
    t_k = temp + KELVIN
    return p_dry / (R_DRY_AIR * t_k) + e / (R_WATER_VAPOR * t_k)


# ---------------------------------------------------------------------------
# Felt temperatures
# ---------------------------------------------------------------------------


def heat_index(temp: float, humidity: float) -> float:
    """Heat index in °C (NOAA / Rothfusz regression with adjustments)."""
    t = temp * 9 / 5 + 32
    rh = humidity
    hi = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (hi + t) / 2 >= 80:
        hi = (
            -42.379
            + 2.04901523 * t
            + 10.14333127 * rh
            - 0.22475541 * t * rh
            - 0.00683783 * t * t
            - 0.05481717 * rh * rh
            + 0.00122874 * t * t * rh
            + 0.00085282 * t * rh * rh
            - 0.00000199 * t * t * rh * rh
        )
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t - 95)) / 17)
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh - 85) / 10) * ((87 - t) / 5)
    return (hi - 32) * 5 / 9


def humidex(temp: float, humidity: float) -> float:
    """Canadian humidex in °C."""
    td = dew_point(temp, humidity)
    e = 6.11 * math.exp(5417.7530 * (1 / 273.16 - 1 / (KELVIN + td)))
    return temp + 0.5555 * (e - 10)


def wind_chill(temp: float, wind_kmh: float) -> float:
    """Wind chill in °C (JAG/TI 2001). Returns the air temperature outside its domain."""
    if temp > 10 or wind_kmh <= 4.8:
        return temp
    v = wind_kmh**0.16
    return 13.12 + 0.6215 * temp - 11.37 * v + 0.3965 * temp * v


def apparent_temperature(temp: float, humidity: float, wind_ms: float) -> float:
    """Apparent temperature in °C (Steadman / Australian BoM, shade)."""
    return temp + 0.33 * vapor_pressure(temp, humidity) - 0.70 * wind_ms - 4.00


def feels_like(temp: float, humidity: float, wind_kmh: float) -> float:
    """Felt temperature in °C, NWS style: wind chill when cold, heat index when hot."""
    if temp <= 10 and wind_kmh > 4.8:
        return wind_chill(temp, wind_kmh)
    if temp >= 26.7:
        return max(temp, heat_index(temp, humidity))
    return temp


def discomfort_index(temp: float, humidity: float) -> float:
    """Thom discomfort index in °C."""
    return temp - 0.55 * (1 - 0.01 * humidity) * (temp - 14.5)


# ---------------------------------------------------------------------------
# Pressure / atmosphere
# ---------------------------------------------------------------------------


def pressure_at_altitude(altitude: float) -> float:
    """Standard atmosphere pressure in hPa at the given altitude (m)."""
    return STANDARD_PRESSURE * (1 - 2.25577e-5 * altitude) ** 5.25588


def sea_level_pressure(pressure: float, altitude: float, temp: float) -> float:
    """Reduce a station pressure (hPa) to mean sea level."""
    gh = 0.0065 * altitude
    return pressure * (1 - gh / (temp + gh + KELVIN)) ** -5.257


def station_pressure(sea_level: float, altitude: float, temp: float) -> float:
    """Inverse of :func:`sea_level_pressure`."""
    gh = 0.0065 * altitude
    return sea_level * (1 - gh / (temp + gh + KELVIN)) ** 5.257


def cloud_base(temp: float, dew: float) -> float:
    """Estimated cumulus cloud base height above ground in m (Espy)."""
    return max(0.0, 125 * (temp - dew))


def beaufort(wind_kmh: float) -> int:
    """Beaufort force (0-12)."""
    wind_ms = wind_kmh / 3.6
    for force, limit in enumerate(_BEAUFORT_LIMITS_MS):
        if wind_ms < limit:
            return force
    return 12


# ---------------------------------------------------------------------------
# Thermal comfort (ISO 7730)
# ---------------------------------------------------------------------------


def pmv_ppd(
    temp: float,
    radiant: float,
    air_speed: float,
    humidity: float,
    met: float,
    clo: float,
    work: float = 0.0,
) -> tuple[float, float]:
    """Predicted Mean Vote and Predicted Percentage Dissatisfied (ISO 7730 algorithm)."""
    pa = humidity * 10 * math.exp(16.6536 - 4030.183 / (temp + 235))
    icl = 0.155 * clo
    m = met * 58.15
    w = work * 58.15
    mw = m - w
    fcl = 1 + 1.29 * icl if icl <= 0.078 else 1.05 + 0.645 * icl
    hcf = 12.1 * math.sqrt(air_speed)
    taa = temp + 273
    tra = radiant + 273
    tcla = taa + (35.5 - temp) / (3.5 * icl + 0.1)

    p1 = icl * fcl
    p2 = p1 * 3.96
    p3 = p1 * 100
    p4 = p1 * taa
    p5 = 308.7 - 0.028 * mw + p2 * (tra / 100) ** 4
    xn = tcla / 100
    xf = tcla / 50
    hc = hcf
    for _ in range(150):
        if abs(xn - xf) <= 0.00015:
            break
        xf = (xf + xn) / 2
        hcn = 2.38 * abs(100 * xf - taa) ** 0.25
        hc = max(hcf, hcn)
        xn = (p5 + p4 * hc - p2 * xf**4) / (100 + p3 * hc)
    else:
        raise ValueError("PMV iteration did not converge")

    tcl = 100 * xn - 273
    hl1 = 3.05 * 0.001 * (5733 - 6.99 * mw - pa)
    hl2 = 0.42 * (mw - 58.15) if mw > 58.15 else 0.0
    hl3 = 1.7e-5 * m * (5867 - pa)
    hl4 = 0.0014 * m * (34 - temp)
    hl5 = 3.96 * fcl * (xn**4 - (tra / 100) ** 4)
    hl6 = fcl * hc * (tcl - temp)
    ts = 0.303 * math.exp(-0.036 * m) + 0.028
    pmv = ts * (mw - hl1 - hl2 - hl3 - hl4 - hl5 - hl6)
    ppd = 100 - 95 * math.exp(-0.03353 * pmv**4 - 0.2179 * pmv**2)
    return pmv, ppd


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def _bucket(value: float, limits: list[float], labels: list[str]) -> str:
    for limit, label in zip(limits, labels, strict=False):
        if value < limit:
            return label
    return labels[-1]


def dew_point_perception(dew: float) -> str:
    """Human perception of the dew point."""
    return _bucket(dew, [10, 13, 16, 18, 21, 24], DEW_POINT_PERCEPTIONS)


def heat_stress(heat_idx: float) -> str:
    """NOAA heat index danger category."""
    return _bucket(heat_idx, [27, 32, 41, 54], HEAT_STRESS_LEVELS)


def wind_chill_risk(chill: float) -> str:
    """Environment Canada frostbite risk category."""
    if chill > -10:
        return "low"
    if chill > -28:
        return "moderate"
    if chill > -40:
        return "high"
    if chill > -48:
        return "very_high"
    if chill > -55:
        return "severe"
    return "extreme"


def co2_level(co2: float) -> str:
    """Indoor air quality category from CO₂ (ppm)."""
    return _bucket(co2, [600, 800, 1000, 1500], CO2_LEVELS)


def mold_risk(surface_humidity: float) -> str:
    """Mold growth risk from the relative humidity at the (coldest) surface."""
    return _bucket(surface_humidity, [70, 80, 90], MOLD_RISKS)


def thermal_sensation(pmv: float) -> str:
    """ASHRAE 7-point thermal sensation scale."""
    index = max(-3, min(3, round(pmv)))
    return THERMAL_SENSATIONS[index + 3]


# ---------------------------------------------------------------------------
# Aggregated computation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Measurements:
    """Normalised source readings (°C, %, hPa, km/h, ppm)."""

    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    wind_speed: float | None = None
    co2: float | None = None
    radiant_temperature: float | None = None
    outdoor_temperature: float | None = None
    outdoor_humidity: float | None = None


@dataclass(slots=True)
class Settings:
    """User tunable parameters."""

    altitude: float = 0.0
    pressure_type: str = PRESSURE_STATION
    temp_min: float = 20.0
    temp_max: float = 24.0
    humidity_min: float = 40.0
    humidity_max: float = 60.0
    co2_max: float = 1000.0
    met: float = 1.2
    clo: float = 0.8
    air_speed: float = 0.1
    frsi: float = 0.7
    mold_threshold: float = 80.0


def comfort_level(temp: float, humidity: float, settings: Settings) -> str:
    """Combined temperature / humidity comfort label."""
    parts = []
    if temp < settings.temp_min:
        parts.append("cold")
    elif temp > settings.temp_max:
        parts.append("hot")
    if humidity < settings.humidity_min:
        parts.append("dry")
    elif humidity > settings.humidity_max:
        parts.append("humid")
    return "_".join(parts) or "comfortable"


def comfort_score(
    temp: float, humidity: float, co2: float | None, settings: Settings
) -> float:
    """Comfort score from 0 (very poor) to 100 (ideal)."""
    score = 100.0
    if temp < settings.temp_min:
        score -= (settings.temp_min - temp) * 12
    elif temp > settings.temp_max:
        score -= (temp - settings.temp_max) * 12
    if humidity < settings.humidity_min:
        score -= (settings.humidity_min - humidity) * 1.5
    elif humidity > settings.humidity_max:
        score -= (humidity - settings.humidity_max) * 1.5
    if co2 is not None and co2 > 800:
        score -= min(40.0, (co2 - 800) / 20)
    return max(0.0, min(100.0, score))


def _r(value: float, digits: int = 2) -> float:
    return round(value, digits)


def compute_all(profile: str, m: Measurements, s: Settings) -> dict[str, Any]:
    """Compute every derived value available from the measurements."""
    out: dict[str, Any] = {}
    if m.temperature is None or m.humidity is None:
        return out

    t = m.temperature
    rh = max(1.0, min(100.0, m.humidity))
    td = dew_point(t, rh)
    hi = heat_index(t, rh)

    if m.pressure is not None:
        if s.pressure_type == PRESSURE_SEA_LEVEL:
            p0 = m.pressure
            p = station_pressure(p0, s.altitude, t)
        else:
            p = m.pressure
            p0 = sea_level_pressure(p, s.altitude, t)
        out["sea_level_pressure"] = _r(p0, 1)
        out["station_pressure"] = _r(p, 1)
    else:
        p = pressure_at_altitude(s.altitude)

    ah = absolute_humidity(t, rh)
    out.update(
        dew_point=_r(td),
        frost_point=_r(frost_point(t, rh)),
        wet_bulb=_r(wet_bulb_temperature(t, rh)),
        absolute_humidity=_r(ah),
        vapor_pressure=_r(vapor_pressure(t, rh)),
        mixing_ratio=_r(mixing_ratio(t, rh, p)),
        specific_humidity=_r(specific_humidity(t, rh, p)),
        enthalpy=_r(enthalpy(t, rh, p)),
        air_density=_r(air_density(t, rh, p), 4),
        heat_index=_r(hi),
        humidex=_r(humidex(t, rh)),
        discomfort_index=_r(discomfort_index(t, rh)),
        dew_point_perception=dew_point_perception(td),
    )

    if profile == PROFILE_OUTDOOR:
        wind = max(0.0, m.wind_speed) if m.wind_speed is not None else None
        if wind is not None:
            wc = wind_chill(t, wind)
            out.update(
                wind_chill=_r(wc),
                apparent_temperature=_r(apparent_temperature(t, rh, wind / 3.6)),
                beaufort=beaufort(wind),
                wind_chill_risk=wind_chill_risk(wc),
            )
        out["feels_like"] = _r(feels_like(t, rh, wind or 0.0))
        out["cloud_base"] = round(cloud_base(t, td))
        out["heat_stress"] = heat_stress(hi)
        out["frost_risk"] = t <= 0 or (t <= 3 and td <= 0)
        out["fog_risk"] = (t - td) <= 1.5 and (wind is None or wind < 15)

    if profile == PROFILE_INDOOR:
        radiant = m.radiant_temperature if m.radiant_temperature is not None else t
        pmv, ppd = pmv_ppd(t, radiant, s.air_speed, rh, s.met, s.clo)
        out.update(
            comfort_level=comfort_level(t, rh, s),
            comfort_score=round(comfort_score(t, rh, m.co2, s)),
            pmv=_r(pmv),
            ppd=_r(ppd, 1),
            thermal_sensation=thermal_sensation(pmv),
        )
        if m.co2 is not None:
            out["co2_level"] = co2_level(m.co2)

        # Coldest surface (thermal bridge) estimation, ISO 13788 temperature factor
        reference_humidity = rh
        if m.outdoor_temperature is not None:
            t_surface = m.outdoor_temperature + s.frsi * (t - m.outdoor_temperature)
            surface_rh = min(
                100.0, 100 * vapor_pressure(t, rh) / saturation_vapor_pressure(t_surface)
            )
            reference_humidity = surface_rh
            out.update(
                surface_temperature=_r(t_surface),
                surface_humidity=_r(surface_rh, 1),
                condensation_alert=t_surface <= td,
            )
        out["mold_risk"] = mold_risk(reference_humidity)
        out["mold_alert"] = reference_humidity >= s.mold_threshold

        reasons = []
        if m.co2 is not None and m.co2 >= s.co2_max:
            reasons.append("co2")
        if m.outdoor_temperature is not None and m.outdoor_humidity is not None:
            out_rh = max(1.0, min(100.0, m.outdoor_humidity))
            ah_out = absolute_humidity(m.outdoor_temperature, out_rh)
            out["outdoor_absolute_humidity"] = _r(ah_out)
            if rh > s.humidity_max and ah_out < ah - VENTILATION_HUMIDITY_MARGIN:
                reasons.append("humidity")
        if (
            m.outdoor_temperature is not None
            and t > s.temp_max
            and m.outdoor_temperature < t - VENTILATION_COOLING_MARGIN
        ):
            reasons.append("cooling")
        out["ventilation"] = bool(reasons)
        out["ventilation_reasons"] = reasons

    return out
