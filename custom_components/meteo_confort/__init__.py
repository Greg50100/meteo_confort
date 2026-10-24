"""Météo & Confort: derived weather and indoor comfort sensors."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .hub import STORAGE_VERSION, MeteoConfortHub, storage_key

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type MeteoConfortConfigEntry = ConfigEntry[MeteoConfortHub]


async def async_setup_entry(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> bool:
    """Set up a Météo & Confort entry."""
    hub = MeteoConfortHub(hass, entry)
    await hub.async_load()
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(hub.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> bool:
    """Unload a Météo & Confort entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_save()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> None:
    """Delete the stored history of a removed entry."""
    await Store(hass, STORAGE_VERSION, storage_key(entry.entry_id)).async_remove()


async def _async_update_listener(hass: HomeAssistant, entry: MeteoConfortConfigEntry) -> None:
    """Reload when the options change (sensors may appear or disappear)."""
    await hass.config_entries.async_reload(entry.entry_id)
