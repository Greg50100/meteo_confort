"""Calculateur Météo & Confort hors ligne.

Petite application de bureau (tkinter, aucune dépendance) qui réutilise le
moteur de calcul et les traductions de l'intégration Home Assistant pour
saisir des mesures à la main :

    python tools/calculateur.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "meteo_confort"


def _load_calculations() -> Any:
    # Loaded by path: the package __init__ imports Home Assistant
    spec = importlib.util.spec_from_file_location(
        "meteo_calculations", INTEGRATION / "calculations.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_translations() -> dict[str, Any]:
    try:
        return json.loads((INTEGRATION / "translations" / "fr.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


calc = _load_calculations()
T = _load_translations()

OUTDOOR, INDOOR = calc.PROFILE_OUTDOOR, calc.PROFILE_INDOOR

# (key, unit, required)
MEASUREMENT_FIELDS = {
    OUTDOOR: [
        ("temperature", "°C", True),
        ("humidity", "%", True),
        ("pressure", "hPa", False),
        ("wind_speed", "km/h", False),
    ],
    INDOOR: [
        ("temperature", "°C", True),
        ("humidity", "%", True),
        ("co2", "ppm", False),
        ("radiant_temperature", "°C", False),
        ("outdoor_temperature", "°C", False),
        ("outdoor_humidity", "%", False),
    ],
}
SETTING_FIELDS = {
    OUTDOOR: [("altitude", "m"), ("pressure_type", "")],
    INDOOR: [
        ("temp_min", "°C"),
        ("temp_max", "°C"),
        ("humidity_min", "%"),
        ("humidity_max", "%"),
        ("co2_max", "ppm"),
        ("met", "met"),
        ("clo", "clo"),
        ("air_speed", "m/s"),
        ("frsi", ""),
        ("mold_threshold", "%"),
    ],
}
HUMIDITY_FIELDS = {"humidity", "outdoor_humidity", "humidity_min", "humidity_max", "mold_threshold"}
EXAMPLES = {
    OUTDOOR: {"temperature": "-2", "humidity": "90", "pressure": "1013", "wind_speed": "25"},
    INDOOR: {
        "temperature": "20",
        "humidity": "68",
        "co2": "1150",
        "outdoor_temperature": "3",
        "outdoor_humidity": "85",
    },
}

GROUPS = [
    (
        "Humidité",
        [
            "dew_point",
            "frost_point",
            "wet_bulb",
            "absolute_humidity",
            "outdoor_absolute_humidity",
            "vapor_pressure",
            "mixing_ratio",
            "specific_humidity",
            "dew_point_perception",
        ],
    ),
    (
        "Températures ressenties",
        [
            "feels_like",
            "heat_index",
            "humidex",
            "wind_chill",
            "apparent_temperature",
            "discomfort_index",
            "heat_stress",
            "wind_chill_risk",
        ],
    ),
    (
        "Atmosphère",
        ["sea_level_pressure", "station_pressure", "air_density", "enthalpy", "cloud_base", "beaufort"],
    ),
    (
        "Confort intérieur",
        ["comfort_level", "comfort_score", "pmv", "ppd", "thermal_sensation", "co2_level"],
    ),
    (
        "Parois et aération",
        [
            "surface_temperature",
            "surface_humidity",
            "mold_risk",
            "mold_alert",
            "condensation_alert",
            "ventilation",
            "ventilation_reasons",
        ],
    ),
    ("Alertes", ["frost_risk", "fog_risk"]),
]

UNITS = {
    **dict.fromkeys(
        [
            "dew_point",
            "frost_point",
            "wet_bulb",
            "heat_index",
            "humidex",
            "discomfort_index",
            "feels_like",
            "wind_chill",
            "apparent_temperature",
            "surface_temperature",
        ],
        "°C",
    ),
    **dict.fromkeys(["absolute_humidity", "outdoor_absolute_humidity"], "g/m³"),
    **dict.fromkeys(["vapor_pressure", "sea_level_pressure", "station_pressure"], "hPa"),
    **dict.fromkeys(["mixing_ratio", "specific_humidity"], "g/kg"),
    **dict.fromkeys(["comfort_score", "ppd", "surface_humidity"], "%"),
    "enthalpy": "kJ/kg",
    "air_density": "kg/m³",
    "cloud_base": "m",
    "beaufort": "Bft",
}
DECIMALS = {
    "absolute_humidity": 2,
    "outdoor_absolute_humidity": 2,
    "vapor_pressure": 2,
    "mixing_ratio": 2,
    "specific_humidity": 2,
    "air_density": 3,
    "pmv": 2,
    "surface_humidity": 0,
}


# ---------------------------------------------------------------------------
# Labels taken from the integration translations
# ---------------------------------------------------------------------------


def _field_texts(kind: str) -> dict[str, str]:
    texts: dict[str, str] = {}
    for step in T.get("config", {}).get("step", {}).values():
        texts.update(step.get(kind, {}))
        texts.update(step.get("sections", {}).get("settings", {}).get(kind, {}))
    return texts


FIELD_LABELS = _field_texts("data")
FIELD_HELP = _field_texts("data_description")
PROFILE_LABELS = T.get("config", {}).get("step", {}).get("user", {}).get("menu_options", {})
PRESSURE_TYPES = T.get("selector", {}).get("pressure_type", {}).get("options", {}) or {
    calc.PRESSURE_STATION: calc.PRESSURE_STATION,
    calc.PRESSURE_SEA_LEVEL: calc.PRESSURE_SEA_LEVEL,
}
_ENTITIES = T.get("entity", {})
VENTILATION_REASONS = (
    _ENTITIES.get("binary_sensor", {})
    .get("ventilation", {})
    .get("state_attributes", {})
    .get("reasons", {})
    .get("state", {})
)


def entity_name(key: str) -> str:
    """French entity name, as shown in Home Assistant."""
    if key == "ventilation_reasons":
        return "Raisons de l'aération"
    for platform in ("sensor", "binary_sensor"):
        if key in _ENTITIES.get(platform, {}):
            return _ENTITIES[platform][key].get("name", key)
    return key


def state_label(key: str, value: str) -> str:
    """French label of an enum state."""
    return _ENTITIES.get("sensor", {}).get(key, {}).get("state", {}).get(value, value)


def format_value(key: str, value: Any) -> str:
    """Human readable value with unit, French decimal comma."""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, list):
        return ", ".join(VENTILATION_REASONS.get(v, v) for v in value) or "—"
    if isinstance(value, str):
        return state_label(key, value)
    if isinstance(value, float):
        text = f"{value:.{DECIMALS.get(key, 1)}f}".replace(".", ",")
    else:
        text = str(value)
    unit = UNITS.get(key)
    return f"{text} {unit}" if unit else text


def parse_number(raw: str) -> float | None:
    """Parse '21,5' or '21.5'; empty string means no value."""
    raw = raw.strip().replace(",", ".")
    return float(raw) if raw else None


def fr(value: float, digits: int = 1) -> str:
    """Number with a French decimal comma."""
    return f"{value:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Psychrometric chart
# ---------------------------------------------------------------------------

CHART_T_MIN, CHART_T_MAX, CHART_W_MAX = -10.0, 45.0, 30.0
CHART_RH_LABEL_TEMP = 30.0
COLOR_SATURATION = "#1f4e79"
COLOR_RH = "#7a9cc6"
COLOR_ENTHALPY = "#b5b5b5"
COLOR_GRID = "#ededed"
COLOR_COMFORT = "#dcf0dc"
COLOR_COMFORT_EDGE = "#2e7d32"
POINT_COLORS = {INDOOR: "#d35400", OUTDOOR: "#1565c0", "wall": "#7b1fa2"}
CHART_HINT = "Survolez le diagramme pour lire température, humidité, enthalpie et point de rosée."


def _font(size: int = 8, bold: bool = False) -> tuple[str, int, str]:
    return ("Segoe UI", size, "bold" if bold else "normal")


class PsychroChart(tk.Canvas):
    """Psychrometric chart: dry-bulb temperature (x) against mixing ratio (y)."""

    MARGINS = (16, 34, 64, 46)  # left, top, right, bottom in px

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, background="white", highlightthickness=0, width=560, height=420)
        self.readout = tk.StringVar(value=CHART_HINT)
        self.chart_state: dict[str, Any] = {}
        self.pressure = calc.STANDARD_PRESSURE
        self.box = (0.0, 0.0, 1.0, 1.0)
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _event: self.readout.set(CHART_HINT))

    def show(self, state: dict[str, Any]) -> None:
        """Draw the chart for the given points, comfort zone and pressure."""
        self.chart_state = state
        self.pressure = state.get("pressure", calc.STANDARD_PRESSURE)
        self.redraw()

    # -- geometry ----------------------------------------------------------

    def _x(self, temp: float) -> float:
        left, _, right, _ = self.box
        return left + (temp - CHART_T_MIN) / (CHART_T_MAX - CHART_T_MIN) * (right - left)

    def _y(self, w: float) -> float:
        _, top, _, bottom = self.box
        return bottom - w / CHART_W_MAX * (bottom - top)

    def _coords(self, points: list[tuple[float, float]]) -> list[float]:
        return [c for temp, w in points for c in (self._x(temp), self._y(w))]

    def _ratio(self, temp: float, rh: float) -> float:
        return calc.mixing_ratio(temp, rh, self.pressure)

    def _rh_curve(self, rh: float) -> list[tuple[float, float]]:
        """Constant relative humidity curve, clipped at the top of the chart."""
        points: list[tuple[float, float]] = []
        temp = CHART_T_MIN
        while temp <= CHART_T_MAX + 1e-9:
            w = self._ratio(temp, rh)
            if w > CHART_W_MAX:
                t0, w0 = points[-1]
                points.append((t0 + (CHART_W_MAX - w0) * (temp - t0) / (w - w0), CHART_W_MAX))
                break
            points.append((temp, w))
            temp += 0.5
        return points

    @staticmethod
    def _w_at_enthalpy(h: float, temp: float) -> float:
        return (h - 1.006 * temp) / (2501 + 1.86 * temp) * 1000

    def _enthalpy_line(self, h: float) -> list[tuple[float, float]]:
        """Constant enthalpy line from dry air (W = 0) up to saturation."""
        t_dry = min(h / 1.006, CHART_T_MAX)
        if t_dry < CHART_T_MIN:
            return []
        low, high = -40.0, t_dry
        for _ in range(40):  # bisection on the saturation crossing
            mid = (low + high) / 2
            if self._w_at_enthalpy(h, mid) > self._ratio(mid, 100):
                low = mid
            else:
                high = mid
        steps = 30
        points = []
        for i in range(steps + 1):
            temp = high + (t_dry - high) * i / steps
            w = self._w_at_enthalpy(h, temp)
            if temp >= CHART_T_MIN and 0 <= w <= CHART_W_MAX:
                points.append((temp, w))
        return points

    # -- drawing -----------------------------------------------------------

    def _label(
        self, x: float, y: float, text: str, color: str, anchor: str, size: int = 8, bold: bool = False
    ) -> None:
        item = self.create_text(x, y, text=text, fill=color, anchor=anchor, font=_font(size, bold))
        x0, y0, x1, y1 = self.bbox(item)
        self.tag_lower(self.create_rectangle(x0 - 2, y0, x1 + 2, y1, fill="white", outline=""), item)

    def _in_chart(self, temp: float, w: float) -> bool:
        return CHART_T_MIN <= temp <= CHART_T_MAX and 0 <= w <= CHART_W_MAX

    def redraw(self) -> None:
        """Redraw everything at the current canvas size."""
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 50 or height < 50:
            return
        m_left, m_top, m_right, m_bottom = self.MARGINS
        self.box = left, top, right, bottom = (m_left, m_top, width - m_right, height - m_bottom)
        zone = self._comfort_polygon()

        if zone:
            self.create_polygon(self._coords(zone), fill=COLOR_COMFORT, outline="")
        for temp in range(int(CHART_T_MIN), int(CHART_T_MAX) + 1, 5):
            x = self._x(temp)
            self.create_line(x, top, x, bottom, fill=COLOR_GRID)
            self.create_text(x, bottom + 5, text=str(temp), anchor="n", font=_font())
        for w in range(0, int(CHART_W_MAX) + 1, 5):
            y = self._y(w)
            self.create_line(left, y, right, y, fill=COLOR_GRID)
            self.create_text(right + 6, y, text=str(w), anchor="w", font=_font())

        enthalpy_labels = []
        for h in range(-10, 131, 10):
            if len(line := self._enthalpy_line(h)) >= 2:
                self.create_line(self._coords(line), fill=COLOR_ENTHALPY, dash=(4, 3))
                enthalpy_labels.append((h, line[0]))

        rh_labels = []
        for rh in range(10, 100, 10):
            curve = self._rh_curve(rh)
            self.create_line(self._coords(curve), fill=COLOR_RH, smooth=True)
            label_temp = min(CHART_RH_LABEL_TEMP, curve[-1][0] - 2)
            rh_labels.append((rh, label_temp, self._ratio(label_temp, rh)))

        # Hide the grid above the saturation curve, then draw the curve itself
        saturation = self._rh_curve(100)
        self.create_polygon(
            self._coords([*saturation, (CHART_T_MIN, CHART_W_MAX)]), fill="white", outline=""
        )
        self.create_line(self._coords(saturation), fill=COLOR_SATURATION, width=2, smooth=True)
        if zone:
            self.create_polygon(self._coords(zone), fill="", outline=COLOR_COMFORT_EDGE, width=1.5)
        self.create_rectangle(left, top, right, bottom, outline="#9e9e9e")

        for h, (temp, w) in enthalpy_labels:
            if w < CHART_W_MAX - 0.5:
                self.create_text(
                    self._x(temp) - 3, self._y(w) - 2, text=str(h), anchor="se",
                    fill="#8a8a8a", font=_font(7),
                )
        for rh, temp, w in rh_labels:
            self._label(self._x(temp), self._y(w), f"{rh} %", COLOR_RH, "center", size=7)

        self.create_text(
            left, top - 18, anchor="w", font=_font(10, True),
            text=f"Diagramme psychrométrique · {fr(self.pressure, 0)} hPa",
        )
        self.create_text(
            (left + right) / 2, bottom + 24, anchor="n", font=_font(9),
            text="Température sèche (°C)",
        )
        self.create_text(
            right + 46, (top + bottom) / 2, angle=90, font=_font(9),
            text="Rapport de mélange (g/kg d'air sec)",
        )

        self._draw_state()

    def _comfort_polygon(self) -> list[tuple[float, float]]:
        if not (zone := self.chart_state.get("comfort")):
            return []
        t_min, t_max, rh_min, rh_max = zone
        if t_min >= t_max or rh_min >= rh_max:
            return []
        temps = [t_min + (t_max - t_min) * i / 20 for i in range(21)]
        lower = [(t, min(self._ratio(t, max(rh_min, 0.1)), CHART_W_MAX)) for t in temps]
        upper = [(t, min(self._ratio(t, rh_max), CHART_W_MAX)) for t in reversed(temps)]
        return lower + upper

    def _marker(self, temp: float, w: float, color: str, radius: float = 5) -> bool:
        if not self._in_chart(temp, w):
            return False
        x, y = self._x(temp), self._y(w)
        self.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="white", width=1.5)
        return True

    def _draw_state(self) -> None:
        points = self.chart_state.get("points", [])
        legend: list[tuple[str, str, str]] = []

        if points and (dew := self.chart_state.get("dew")):
            temp, rh, dew_point = dew
            w = self._ratio(temp, rh)
            wall = self.chart_state.get("wall")
            line_end = min(dew_point, wall) if wall is not None else dew_point
            if 0 <= w <= CHART_W_MAX:
                self.create_line(
                    self._x(max(line_end, CHART_T_MIN)), self._y(w), self._x(min(temp, CHART_T_MAX)), self._y(w),
                    fill="#616161", dash=(2, 2),
                )
                if self._marker(dew_point, w, "white", radius=4):
                    x, y = self._x(dew_point), self._y(w)
                    self.create_oval(x - 4, y - 4, x + 4, y + 4, outline=COLOR_SATURATION, width=1.5)
                    self._label(x - 6, y - 6, f"Td {fr(dew_point)} °C", COLOR_SATURATION, "se")
                if wall is not None and self._marker(wall, w, POINT_COLORS["wall"]):
                    self._label(
                        self._x(wall), self._y(w) + 8, f"Paroi {fr(wall)} °C",
                        POINT_COLORS["wall"], "n", bold=True,
                    )
                    legend.append(("dot", POINT_COLORS["wall"], "Paroi froide (même humidité)"))

        point_legend = []
        for name, temp, rh, color in points:
            w = self._ratio(temp, rh)
            if self._marker(temp, w, color, radius=6):
                text = f"{name} {fr(temp)} °C · {rh:.0f} %"
                self._label(self._x(temp) + 8, self._y(w) - 8, text, color, "sw", bold=True)
                point_legend.append(("dot", color, name))
            else:
                point_legend.append(("dot", color, f"{name} (hors du diagramme)"))
        legend = point_legend + legend

        if self.chart_state.get("comfort"):
            legend.append(("box", COLOR_COMFORT_EDGE, "Zone de confort"))
        legend += [
            ("line", COLOR_RH, "Humidité relative"),
            ("dash", COLOR_ENTHALPY, "Enthalpie (kJ/kg)"),
        ]
        left, top, _, _ = self.box
        x, y = left + 12, top + 12
        for kind, color, text in legend:
            if kind == "dot":
                self.create_oval(x, y - 5, x + 10, y + 5, fill=color, outline="")
            elif kind == "box":
                self.create_rectangle(x, y - 5, x + 10, y + 5, fill=COLOR_COMFORT, outline=color)
            else:
                self.create_line(x - 2, y, x + 12, y, fill=color, width=2, dash=(4, 3) if kind == "dash" else None)
            self.create_text(x + 18, y, text=text, anchor="w", font=_font())
            y += 17

    def _on_motion(self, event: tk.Event) -> None:
        left, top, right, bottom = self.box
        if not (left <= event.x <= right and top <= event.y <= bottom):
            self.readout.set(CHART_HINT)
            return
        temp = CHART_T_MIN + (event.x - left) / (right - left) * (CHART_T_MAX - CHART_T_MIN)
        w = (bottom - event.y) / (bottom - top) * CHART_W_MAX
        e = w * self.pressure / (621.97 + w)
        rh = 100 * e / calc.saturation_vapor_pressure(temp)
        if rh > 100:
            self.readout.set(f"T {fr(temp)} °C · W {fr(w)} g/kg · au-delà de la saturation (condensation)")
            return
        h = 1.006 * temp + w / 1000 * (2501 + 1.86 * temp)
        parts = [f"T {fr(temp)} °C", f"HR {rh:.0f} %", f"W {fr(w)} g/kg", f"h {fr(h)} kJ/kg"]
        if rh >= 1:
            parts.append(f"Td {fr(calc.dew_point(temp, rh))} °C")
        self.readout.set(" · ".join(parts))


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class Calculator(ttk.Frame):
    """Main window content."""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.profile = tk.StringVar(value=INDOOR)
        defaults = calc.Settings()
        self.vars: dict[str, dict[str, tk.StringVar]] = {}
        for profile in (OUTDOOR, INDOOR):
            profile_vars = {key: tk.StringVar() for key, _, _ in MEASUREMENT_FIELDS[profile]}
            for key, _ in SETTING_FIELDS[profile]:
                default = getattr(defaults, key)
                if key == "pressure_type":
                    profile_vars[key] = tk.StringVar(value=PRESSURE_TYPES[default])
                else:
                    profile_vars[key] = tk.StringVar(value=f"{default:g}".replace(".", ","))
            for var in profile_vars.values():
                var.trace_add("write", self.recompute)
            self.vars[profile] = profile_vars
        self.data: dict[str, Any] = {}
        self._build()
        self._build_inputs()
        self.recompute()

    # -- layout ------------------------------------------------------------

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(top, text="Profil :", font=("Segoe UI", 10, "bold")).pack(side="left")
        for profile in (OUTDOOR, INDOOR):
            ttk.Radiobutton(
                top,
                text=PROFILE_LABELS.get(profile, profile),
                value=profile,
                variable=self.profile,
                command=self._on_profile_change,
            ).pack(side="left", padx=8)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsw", padx=(0, 12))
        self.measures_tab = ttk.Frame(notebook, padding=10)
        self.settings_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.measures_tab, text="Mesures")
        notebook.add(self.settings_tab, text="Paramètres")

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self.banner = ttk.Label(right, font=("Segoe UI", 14, "bold"), padding=(4, 0, 4, 8))
        self.banner.grid(row=0, column=0, sticky="w")
        self.views = ttk.Notebook(right)
        self.views.grid(row=1, column=0, sticky="nsew")

        results = ttk.Frame(self.views)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.views.add(results, text="Résultats")
        self.tree = ttk.Treeview(results, columns=("value",), show="tree headings", height=24)
        self.tree.heading("#0", text="Grandeur")
        self.tree.heading("value", text="Valeur")
        self.tree.column("#0", width=300)
        self.tree.column("value", width=220)
        self.tree.tag_configure("group", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("on", foreground="#b3261e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(results, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        chart_tab = ttk.Frame(self.views)
        chart_tab.columnconfigure(0, weight=1)
        chart_tab.rowconfigure(0, weight=1)
        self.views.add(chart_tab, text="Diagramme psychrométrique")
        self.chart = PsychroChart(chart_tab)
        self.chart.grid(row=0, column=0, sticky="nsew")
        ttk.Label(chart_tab, textvariable=self.chart.readout, foreground="#555555", padding=(6, 4)).grid(
            row=1, column=0, sticky="w"
        )

        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(bottom, text="Valeurs d'exemple", command=self.fill_example).pack(side="left")
        ttk.Button(bottom, text="Effacer les mesures", command=self.clear).pack(side="left", padx=6)
        ttk.Button(bottom, text="Copier les résultats", command=self.copy).pack(side="left")
        self.status = ttk.Label(bottom, foreground="#555555")
        self.status.pack(side="left", padx=12)

    def _build_inputs(self) -> None:
        for tab in (self.measures_tab, self.settings_tab):
            for child in tab.winfo_children():
                child.destroy()
        profile = self.profile.get()
        profile_vars = self.vars[profile]

        row = 0
        for key, unit, required in MEASUREMENT_FIELDS[profile]:
            label = FIELD_LABELS.get(key, key) + (" *" if required else "")
            row = self._add_field(self.measures_tab, row, key, label, unit, profile_vars[key])
        ttk.Label(
            self.measures_tab,
            text="* obligatoire. Laissez vide un capteur que vous n'avez pas.",
            foreground="#666666",
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 0))

        row = 0
        for key, unit in SETTING_FIELDS[profile]:
            label = FIELD_LABELS.get(key, key)
            if key == "pressure_type":
                ttk.Label(self.settings_tab, text=label).grid(row=row, column=0, sticky="w", pady=3)
                ttk.Combobox(
                    self.settings_tab,
                    textvariable=profile_vars[key],
                    values=list(PRESSURE_TYPES.values()),
                    state="readonly",
                    width=34,
                ).grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
                row += 1
                row = self._add_help(self.settings_tab, row, key)
                continue
            row = self._add_field(self.settings_tab, row, key, label, unit, profile_vars[key])

    def _add_field(
        self, tab: ttk.Frame, row: int, key: str, label: str, unit: str, var: tk.StringVar
    ) -> int:
        ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(tab, textvariable=var, width=10, justify="right").grid(
            row=row, column=1, sticky="w", padx=6, pady=3
        )
        ttk.Label(tab, text=unit, foreground="#666666").grid(row=row, column=2, sticky="w")
        return self._add_help(tab, row + 1, key)

    def _add_help(self, tab: ttk.Frame, row: int, key: str) -> int:
        if help_text := FIELD_HELP.get(key):
            ttk.Label(
                tab, text=help_text, foreground="#777777", wraplength=330, font=("Segoe UI", 8)
            ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
            return row + 1
        return row

    # -- actions -----------------------------------------------------------

    def _on_profile_change(self) -> None:
        self._build_inputs()
        self.recompute()

    def fill_example(self) -> None:
        """Fill the measurements with a demonstrative case."""
        profile = self.profile.get()
        for key, _, _ in MEASUREMENT_FIELDS[profile]:
            self.vars[profile][key].set(EXAMPLES[profile].get(key, ""))

    def clear(self) -> None:
        """Empty the measurement fields of the current profile."""
        profile = self.profile.get()
        for key, _, _ in MEASUREMENT_FIELDS[profile]:
            self.vars[profile][key].set("")

    def copy(self) -> None:
        """Copy the results as plain text."""
        if not self.data:
            self.status.configure(text="Rien à copier.")
            return
        lines = [f"Météo & Confort — {PROFILE_LABELS.get(self.profile.get(), '')}"]
        for title, keys in self._groups():
            lines.append(f"\n{title}")
            lines += [f"  {entity_name(k)} : {format_value(k, self.data[k])}" for k in keys]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.status.configure(text="Résultats copiés dans le presse-papiers.")

    # -- computation -------------------------------------------------------

    def read_inputs(self) -> tuple[Any, Any, list[str]]:
        """Return (Measurements, Settings, problems)."""
        profile = self.profile.get()
        profile_vars = self.vars[profile]
        problems: list[str] = []
        measurements: dict[str, float] = {}
        settings: dict[str, Any] = {}

        for key, _, required in MEASUREMENT_FIELDS[profile]:
            label = FIELD_LABELS.get(key, key)
            try:
                value = parse_number(profile_vars[key].get())
            except ValueError:
                problems.append(f"{label} invalide")
                continue
            if value is None:
                if required:
                    problems.append(f"{label} manquante")
                continue
            if key in HUMIDITY_FIELDS and not 0 <= value <= 100:
                problems.append(f"{label} hors de 0–100 %")
                continue
            measurements[key] = value

        reverse_pressure = {v: k for k, v in PRESSURE_TYPES.items()}
        for key, _ in SETTING_FIELDS[profile]:
            raw = profile_vars[key].get()
            if key == "pressure_type":
                settings[key] = reverse_pressure.get(raw, calc.PRESSURE_STATION)
                continue
            try:
                value = parse_number(raw)
            except ValueError:
                value = None
            if value is None:
                problems.append(f"{FIELD_LABELS.get(key, key)} invalide")
                continue
            settings[key] = value

        return calc.Measurements(**measurements), calc.Settings(**settings), problems

    def recompute(self, *_: Any) -> None:
        """Recalculate everything from the current fields."""
        measurements, settings, problems = self.read_inputs()
        self.data = {}
        if not problems:
            try:
                self.data = calc.compute_all(self.profile.get(), measurements, settings)
            except (ValueError, ZeroDivisionError, OverflowError) as err:
                problems.append(f"calcul impossible ({err})")
        self.status.configure(
            text=" · ".join(problems) if problems else f"{len(self.data)} valeurs calculées"
        )
        self._show()
        self._update_chart(measurements, settings)

    def _comfort_zone(self) -> tuple[float, float, float, float]:
        """Comfort zone from the indoor settings, shown for both profiles."""
        defaults = calc.Settings()
        values = []
        for key in ("temp_min", "temp_max", "humidity_min", "humidity_max"):
            try:
                value = parse_number(self.vars[INDOOR][key].get())
            except ValueError:
                value = None
            values.append(value if value is not None else getattr(defaults, key))
        return tuple(values)

    def _update_chart(self, measurements: Any, settings: Any) -> None:
        profile = self.profile.get()
        data = self.data
        state: dict[str, Any] = {
            "pressure": data.get("station_pressure") or calc.pressure_at_altitude(settings.altitude),
            "comfort": self._comfort_zone(),
            "points": [],
        }
        if data:
            rh = max(1.0, min(100.0, measurements.humidity))
            name = "Intérieur" if profile == INDOOR else "Extérieur"
            state["points"].append((name, measurements.temperature, rh, POINT_COLORS[profile]))
            state["dew"] = (measurements.temperature, rh, data["dew_point"])
            state["wall"] = data.get("surface_temperature")
            outdoor_t, outdoor_rh = measurements.outdoor_temperature, measurements.outdoor_humidity
            if profile == INDOOR and outdoor_t is not None and outdoor_rh is not None:
                state["points"].append(("Extérieur", outdoor_t, outdoor_rh, POINT_COLORS[OUTDOOR]))
        self.chart.show(state)

    def _groups(self) -> list[tuple[str, list[str]]]:
        known = {k for _, keys in GROUPS for k in keys}
        groups = [(title, [k for k in keys if k in self.data]) for title, keys in GROUPS]
        groups.append(("Autres", [k for k in self.data if k not in known]))
        return [(title, keys) for title, keys in groups if keys]

    def _show(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for title, keys in self._groups():
            parent = self.tree.insert("", "end", text=title, open=True, tags=("group",))
            for key in keys:
                value = self.data[key]
                tags = ("on",) if value is True else ()
                self.tree.insert(parent, "end", text=entity_name(key), values=(format_value(key, value),), tags=tags)
        self._update_banner()

    def _update_banner(self) -> None:
        data = self.data
        if not data:
            self.banner.configure(text="Saisissez au moins la température et l'humidité", foreground="#666666")
        elif "comfort_level" in data:
            score = data["comfort_score"]
            color = "#1b7f3b" if score >= 80 else "#b26a00" if score >= 50 else "#b3261e"
            self.banner.configure(
                text=f"{state_label('comfort_level', data['comfort_level'])} · score {score} %",
                foreground=color,
            )
        else:
            perception = state_label("dew_point_perception", data["dew_point_perception"])
            self.banner.configure(
                text=f"Ressenti {format_value('feels_like', data['feels_like'])} · {perception}",
                foreground="#1f4e79",
            )


def main() -> None:
    """Launch the window."""
    try:  # Crisp text on high DPI Windows screens
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, ImportError, OSError):
        pass
    root = tk.Tk()
    root.title("Calculateur Météo & Confort")
    root.minsize(960, 620)
    Calculator(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
