"""Binary sensor platform for Météo & Confort."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MeteoConfortConfigEntry
from .calculations import PROFILE_INDOOR, PROFILE_OUTDOOR
from .const import CONF_OUTDOOR_TEMPERATURE
from .entity import MeteoConfortEntity, MeteoConfortEntityDescription, is_supported

OUTDOOR = (PROFILE_OUTDOOR,)
INDOOR = (PROFILE_INDOOR,)


@dataclass(frozen=True, kw_only=True)
class MeteoConfortBinarySensorDescription(
    BinarySensorEntityDescription, MeteoConfortEntityDescription
):
    """Binary sensor description."""

    # (attribute name, key in the hub data) pairs explaining the state
    attributes: tuple[tuple[str, str], ...] = ()


BINARY_SENSORS: tuple[MeteoConfortBinarySensorDescription, ...] = (
    MeteoConfortBinarySensorDescription(
        key="frost_risk", device_class=BinarySensorDeviceClass.COLD, profiles=OUTDOOR
    ),
    MeteoConfortBinarySensorDescription(key="fog_risk", profiles=OUTDOOR),
    MeteoConfortBinarySensorDescription(
        key="mold_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        profiles=INDOOR,
        attributes=(
            ("mean_humidity", "mold_humidity"),
            ("window_hours", "mold_window"),
            ("coverage_hours", "mold_coverage"),
        ),
    ),
    MeteoConfortBinarySensorDescription(
        key="condensation_alert",
        device_class=BinarySensorDeviceClass.MOISTURE,
        profiles=INDOOR,
        requires=(CONF_OUTDOOR_TEMPERATURE,),
    ),
    MeteoConfortBinarySensorDescription(
        key="ventilation", profiles=INDOOR, attributes=(("reasons", "ventilation_reasons"),)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoConfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    hub = entry.runtime_data
    async_add_entities(
        MeteoConfortBinarySensor(hub, description)
        for description in BINARY_SENSORS
        if is_supported(description, hub)
    )


class MeteoConfortBinarySensor(MeteoConfortEntity, BinarySensorEntity):
    """A computed binary sensor."""

    entity_description: MeteoConfortBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return the computed state."""
        return self.hub.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the reasons behind the state, when relevant."""
        if not (attributes := self.entity_description.attributes):
            return None
        return {name: self.hub.data.get(key) for name, key in attributes}
