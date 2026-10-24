"""Base entity for Météo & Confort."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.entity import Entity, EntityDescription

from .calculations import PROFILE_INDOOR, PROFILE_OUTDOOR
from .hub import MeteoConfortHub

BOTH = (PROFILE_OUTDOOR, PROFILE_INDOOR)


@dataclass(frozen=True, kw_only=True)
class MeteoConfortEntityDescription(EntityDescription):
    """Describes which profile and source sensors an entity needs."""

    profiles: tuple[str, ...] = BOTH
    requires: tuple[str, ...] = ()
    exists_fn: Callable[[dict[str, Any]], bool] = lambda options: True


def is_supported(description: MeteoConfortEntityDescription, hub: MeteoConfortHub) -> bool:
    """Return True if the entity makes sense for this entry."""
    return (
        hub.profile in description.profiles
        and all(hub.has_input(key) for key in description.requires)
        and description.exists_fn(hub.options)
    )


class MeteoConfortEntity(Entity):
    """Entity whose value comes from the hub's computed data."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: MeteoConfortEntityDescription

    def __init__(self, hub: MeteoConfortHub, description: MeteoConfortEntityDescription) -> None:
        self.hub = hub
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{hub.entry.entry_id}_{description.key}"
        self._attr_device_info = hub.device_info

    @property
    def available(self) -> bool:
        """Available as long as the value could be computed."""
        return self.hub.data.get(self.entity_description.key) is not None

    async def async_added_to_hass(self) -> None:
        """Subscribe to hub updates."""
        self.async_on_remove(self.hub.async_add_listener(self.async_write_ha_state))
