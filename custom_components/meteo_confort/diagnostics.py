"""Diagnostics for Météo & Confort."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import MeteoConfortConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeteoConfortConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data
    return {
        "profile": hub.profile,
        "options": dict(entry.options),
        "settings": asdict(hub.settings),
        "sources": {
            key: (state.state, dict(state.attributes)) if (state := hass.states.get(eid)) else None
            for key, eid in hub.sources.items()
        },
        "data": hub.data,
    }
