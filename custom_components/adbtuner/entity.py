"""Shared entity helpers for ADBTuner."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ADBTunerCoordinator


def server_device(coordinator: ADBTunerCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="ADBTuner",
        manufacturer="ADBTuner",
        model="ADBTuner server",
        sw_version=coordinator.data.version if coordinator.data else None,
        configuration_url=coordinator.client.base_url,
    )


class ADBTunerTunerEntity(CoordinatorEntity[ADBTunerCoordinator]):
    """An entity belonging to one tuner (one streaming device)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.tuner_id = tuner_id
        entry_id = coordinator.config_entry.entry_id
        tuner = coordinator.data.tuners[tuner_id]
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{tuner_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{tuner_id}")},
            name=tuner.get("name") or f"Tuner {tuner_id}",
            manufacturer="ADBTuner",
            model="Tuner",
            configuration_url=coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        return super().available and self.tuner_id in self.coordinator.data.tuners

    @property
    def lock(self) -> dict[str, Any] | None:
        """This tuner's entry in ADBTuner's active-tuner table, if it's in use."""
        return self.coordinator.data.status.get(self.tuner_id)

    @property
    def tuner_state(self) -> str:
        lock = self.lock
        if lock is None:
            return "idle"
        if lock.get("maintenance"):
            return "maintenance"
        return "tuned" if lock.get("tuning_status") == "tuned" else "tuning"

    @property
    def current_channel(self) -> dict[str, Any] | None:
        """The ADBTuner channel this tuner is on, if any."""
        lock = self.lock
        if not lock or lock.get("maintenance"):
            return None
        return self.coordinator.data.channels.get(lock.get("channel_id")) or {
            "id": lock.get("channel_id"),
            "number": lock.get("number"),
            "name": lock.get("name"),
            "provider_name": lock.get("provider_name"),
        }


def ts(value: float | int | None):
    """Convert a Unix timestamp to an aware datetime."""
    return dt_util.utc_from_timestamp(value) if value else None
