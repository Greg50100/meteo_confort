"""Unit tests for the pure calculation module (no Home Assistant needed)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

_PATH = Path(__file__).parents[1] / "custom_components" / "meteo_confort" / "calculations.py"
_SPEC = importlib.util.spec_from_file_location("meteo_calculations", _PATH)
calc = importlib.util.module_from_spec(_SPEC)
sys.modules["meteo_calculations"] = calc
_SPEC.loader.exec_module(calc)


@pytest.mark.parametrize(
    ("temp", "rh", "expected"),
    [(20, 50, 9.3), (30, 70, 23.9), (0, 80, -3.0), (25, 100, 25.0)],
)
def test_dew_point(temp, rh, expected):
    assert calc.dew_point(temp, rh) == pytest.approx(expected, abs=0.1)


def test_frost_point_above_dew_point_when_freezing():
    assert calc.frost_point(-5, 80) > calc.dew_point(-5, 80)
    assert calc.frost_point(20, 50) == calc.dew_point(20, 50)


def test_absolute_humidity():
    # 20 °C / 50 % ≈ 8.6 g/m³
    assert calc.absolute_humidity(20, 50) == pytest.approx(8.64, abs=0.05)


def test_wet_bulb_stull_reference():
    # Reference value from Stull (2011)
    assert calc.wet_bulb_temperature(20, 50) == pytest.approx(13.7, abs=0.1)


def test_heat_index_noaa_table():
    # NOAA table: 90 °F / 70 % → 106 °F (41.1 °C)
    assert calc.heat_index(32.22, 70) == pytest.approx(41.1, abs=0.5)
    # Below the regression domain, heat index stays close to the air temperature
    assert calc.heat_index(20, 50) == pytest.approx(19.6, abs=0.5)


def test_humidex_environment_canada_table():
    # Air 30 °C, dew point 15 °C → humidex 34
    rh = 100 * calc.vapor_pressure(15, 100) / calc.saturation_vapor_pressure(30)
    assert calc.humidex(30, rh) == pytest.approx(34, abs=0.6)


def test_wind_chill_environment_canada_table():
    assert calc.wind_chill(-20, 30) == pytest.approx(-32.6, abs=0.3)
    assert calc.wind_chill(15, 30) == 15
    assert calc.wind_chill(-5, 3) == -5


def test_apparent_temperature():
    assert calc.apparent_temperature(25, 50, 2) == pytest.approx(24.8, abs=0.1)


def test_feels_like_switches_formula():
    assert calc.feels_like(-10, 70, 20) == calc.wind_chill(-10, 20)
    assert calc.feels_like(32, 70, 0) == pytest.approx(calc.heat_index(32, 70))
    assert calc.feels_like(18, 60, 20) == 18


def test_pressure_reduction_round_trip():
    p0 = calc.sea_level_pressure(950, 500, 15)
    assert p0 == pytest.approx(1007.7, abs=0.5)
    assert calc.station_pressure(p0, 500, 15) == pytest.approx(950, abs=0.01)


def test_air_density_standard_conditions():
    assert calc.air_density(15, 0.0001, 1013.25) == pytest.approx(1.225, abs=0.002)


def test_beaufort():
    assert calc.beaufort(0) == 0
    assert calc.beaufort(15) == 3
    assert calc.beaufort(20) == 4
    assert calc.beaufort(60) == 7
    assert calc.beaufort(150) == 12


def test_pmv_iso7730_reference():
    # ISO 7730 Annex D: 22 °C, tr 22 °C, 0.1 m/s, 60 %, 1.2 met, 0.5 clo → PMV -0.75, PPD 17
    pmv, ppd = calc.pmv_ppd(22, 22, 0.1, 60, 1.2, 0.5)
    assert pmv == pytest.approx(-0.75, abs=0.02)
    assert ppd == pytest.approx(17, abs=0.5)


def test_categories():
    assert calc.dew_point_perception(5) == "dry"
    assert calc.dew_point_perception(25) == "oppressive"
    assert calc.heat_stress(30) == "caution"
    assert calc.wind_chill_risk(-30) == "high"
    assert calc.co2_level(450) == "excellent"
    assert calc.co2_level(2000) == "bad"
    assert calc.mold_risk(85) == "high"
    assert calc.thermal_sensation(-0.75) == "slightly_cool"
    assert calc.thermal_sensation(5) == "hot"


def test_comfort_level_and_score():
    s = calc.Settings()
    assert calc.comfort_level(21, 50, s) == "comfortable"
    assert calc.comfort_level(18, 30, s) == "cold_dry"
    assert calc.comfort_level(26, 70, s) == "hot_humid"
    assert calc.comfort_score(21, 50, 500, s) == 100
    assert calc.comfort_score(18, 50, None, s) == 76
    assert calc.comfort_score(10, 95, 3000, s) == 0


def test_compute_all_outdoor():
    m = calc.Measurements(temperature=-2, humidity=95, pressure=1015, wind_speed=10)
    s = calc.Settings(altitude=100, pressure_type=calc.PRESSURE_SEA_LEVEL)
    data = calc.compute_all(calc.PROFILE_OUTDOOR, m, s)
    assert data["sea_level_pressure"] == 1015
    assert data["station_pressure"] < 1015
    assert data["frost_risk"] is True
    assert data["fog_risk"] is True
    assert data["beaufort"] == 2
    assert data["feels_like"] < -2
    assert "comfort_level" not in data


def test_compute_all_indoor_mold_and_ventilation():
    m = calc.Measurements(
        temperature=20, humidity=70, co2=1200, outdoor_temperature=0, outdoor_humidity=90
    )
    data = calc.compute_all(calc.PROFILE_INDOOR, m, calc.Settings())
    # Wall at 0 + 0.7 * 20 = 14 °C, dew point ≈ 14.4 °C → condensation
    assert data["surface_temperature"] == pytest.approx(14)
    assert data["surface_humidity"] == 100
    assert data["condensation_alert"] is True
    assert data["mold_alert"] is True
    assert data["mold_risk"] == "very_high"
    assert data["co2_level"] == "poor"
    assert data["ventilation"] is True
    assert data["ventilation_reasons"] == ["co2", "humidity"]
    assert "wind_chill" not in data


def test_compute_all_indoor_without_optional_sensors():
    m = calc.Measurements(temperature=21, humidity=50)
    data = calc.compute_all(calc.PROFILE_INDOOR, m, calc.Settings())
    assert data["comfort_level"] == "comfortable"
    assert data["ventilation"] is False
    assert data["mold_alert"] is False
    assert "surface_temperature" not in data
    assert "co2_level" not in data


def test_compute_all_missing_inputs():
    assert calc.compute_all(calc.PROFILE_INDOOR, calc.Measurements(temperature=20), calc.Settings()) == {}
