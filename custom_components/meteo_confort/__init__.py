"""Météo & Confort: derived weather and indoor comfort sensors."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .hub import MeteoConfortHub

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type MeteoConfortConfigEntry = ConfigEntry[MeteoConfortHub]


async def async_setup_entry(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> bool:
    """Set up a Météo & Confort entry."""
    hub = MeteoConfortHub(hass, entry)
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(hub.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> bool:
    """Unload a Météo & Confort entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> None:
    """Reload when the options change (sensors may appear or disappear)."""
    await hass.config_entries.async_reload(entry.entry_id)
