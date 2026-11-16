"""Sensor platform for Nexprint."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NexprintConfigEntry
from .api import NexprintAccountData
from .const import BASE_URL, DOMAIN
from .coordinator import NexprintCoordinator


@dataclass(frozen=True, kw_only=True)
class NexprintSensorDescription(SensorEntityDescription):
    """Describes a Nexprint account sensor."""

    value_fn: Callable[[NexprintAccountData], Any]
    attr_fn: Callable[[NexprintAccountData], dict[str, Any]] | None = None


SENSORS: tuple[NexprintSensorDescription, ...] = (
    NexprintSensorDescription(
        key="profile",
        name="Profile",
        icon="mdi:account-circle",
        value_fn=lambda d: d.nickname,
        attr_fn=lambda d: {
            "user_id": d.user_id,
            "email": d.email,
            "country": d.country_name,
            "printers": d.printers,
            "avatar_url": d.avatar_url,
        },
    ),
    NexprintSensorDescription(
        key="unread_messages",
        name="Unread messages",
        icon="mdi:bell-badge-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.unread_messages_total,
        attr_fn=lambda d: {
            "system": d.unread_system,
            "comments": d.unread_comments,
            "following": d.unread_following,
            "activity": d.unread_activity,
            "models": d.unread_models,
        },
    ),
    NexprintSensorDescription(
        key="published_models",
        name="Published models",
        icon="mdi:cube-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.published_models,
    ),
    NexprintSensorDescription(
        key="followers",
        name="Followers",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.followers,
        attr_fn=lambda d: {
            "following": d.following,
        },
    ),
    NexprintSensorDescription(
        key="total_likes",
        name="Total likes",
        icon="mdi:heart",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.total_likes,
        attr_fn=lambda d: {
            "favorites": d.total_favorites,
        },
    ),
    NexprintSensorDescription(
        key="total_downloads",
        name="Total downloads",
        icon="mdi:download",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.total_downloads,
        attr_fn=lambda d: {
            "prints": d.total_prints,
        },
    ),
    NexprintSensorDescription(
        key="creator_points",
        name="Creator points",
        icon="mdi:star-circle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.points_balance,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NexprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nexprint sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        NexprintSensor(coordinator, entry, description) for description in SENSORS
    )


class NexprintSensor(CoordinatorEntity[NexprintCoordinator], SensorEntity):
    """Sensor representing a Nexprint user profile or notification metric."""

    _attr_has_entity_name = True
    entity_description: NexprintSensorDescription

    def __init__(
        self,
        coordinator: NexprintCoordinator,
        entry: NexprintConfigEntry,
        description: NexprintSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        account = coordinator.data
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"user_{account.user_id}")},
            name=f"Nexprint ({account.nickname})",
            manufacturer="Elegoo",
            model="Nexprint Account",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{BASE_URL}/en/user/{account.user_id}",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)
        return None
