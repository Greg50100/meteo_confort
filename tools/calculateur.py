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
        self.banner.grid(row=0, column=0, columnspan=2, sticky="w")
        self.tree = ttk.Treeview(right, columns=("value",), show="tree headings", height=24)
        self.tree.heading("#0", text="Grandeur")
        self.tree.heading("value", text="Valeur")
        self.tree.column("#0", width=300)
        self.tree.column("value", width=220)
        self.tree.tag_configure("group", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("on", foreground="#b3261e")
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

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
