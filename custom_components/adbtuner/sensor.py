"""Sensors for ADBTuner."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import ADBTunerConfigEntry
from .const import TUNER_STATES
from .coordinator import ADBTunerCoordinator, GuideCoordinator
from .entity import ADBTunerTunerEntity, server_device, ts
from .xmltv import programme_at


async def async_setup_entry(
    hass: HomeAssistant, entry: ADBTunerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[SensorEntity] = [ServerVersionSensor(coordinator)]
    for tuner_id in coordinator.data.tuners:
        entities += [
            TunerStatusSensor(coordinator, tuner_id),
            TunerChannelSensor(coordinator, tuner_id),
            TunerLastTuneSensor(coordinator, tuner_id),
        ]
        if runtime.guide:
            entities.append(TunerNowPlayingSensor(coordinator, tuner_id, runtime.guide))
    async_add_entities(entities)


class ServerVersionSensor(CoordinatorEntity[ADBTunerCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ADBTunerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_version"
        self._attr_device_info = server_device(coordinator)

    @property
    def native_value(self) -> str:
        return self.coordinator.data.version


class TunerStatusSensor(ADBTunerTunerEntity, SensorEntity):
    """idle / tuning / tuned / maintenance."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = TUNER_STATES

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "status")

    @property
    def native_value(self) -> str:
        return self.tuner_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lock = self.lock or {}
        channel = self.current_channel or {}
        return {
            "channel_number": channel.get("number"),
            "channel_name": channel.get("name"),
            "provider": channel.get("provider_name"),
            "since": ts(lock.get("lock_obtained")),
            "message": lock.get("full_message"),
            "device_ip_address": self.coordinator.data.tuners[self.tuner_id].get("device_ip_address"),
        }


class TunerChannelSensor(ADBTunerTunerEntity, SensorEntity):
    """The channel currently tuned, e.g. '2306 Peacock (Web) 06'."""

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "channel")

    @property
    def native_value(self) -> str | None:
        channel = self.current_channel
        if not channel:
            return None
        return " ".join(str(p) for p in (channel.get("number"), channel.get("name")) if p)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        channel = self.current_channel or {}
        return {k: channel.get(k) for k in ("number", "name", "provider_name", "m3u_id")}


class TunerLastTuneSensor(ADBTunerTunerEntity, SensorEntity):
    """Result of the most recent tune attempt on this tuner."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "last_tune")

    @property
    def _activity(self) -> dict[str, Any] | None:
        return self.coordinator.data.last_activity(self.tuner_id)

    @property
    def native_value(self) -> str | None:
        act = self._activity
        return act.get("status") if act else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        act = self._activity or {}
        started, streaming = act.get("started_at"), act.get("streaming_at")
        return {
            "channel": " ".join(str(p) for p in (act.get("channel_number"), act.get("channel_name")) if p) or None,
            "provider": act.get("provider_name"),
            "configuration": act.get("configuration_name"),
            "started": ts(started),
            "ended": ts(act.get("ended_at")),
            "seconds_to_stream": round(streaming - started, 1) if started and streaming else None,
            "client": act.get("client_user_agent"),
            "error": act.get("error"),
        }


class TunerNowPlayingSensor(ADBTunerTunerEntity, SensorEntity):
    """Guide title of what's on the tuned channel right now."""

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int, guide: GuideCoordinator) -> None:
        super().__init__(coordinator, tuner_id, "now_playing")
        self.guide = guide

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.guide.async_add_listener(self._handle_coordinator_update))

    def _programme(self):
        channel = self.current_channel
        if not channel or not self.guide.data:
            return None
        prog = programme_at(self.guide.data.get(channel.get("m3u_id") or ""), dt_util.utcnow())
        return None if prog is None or prog.is_idle else prog

    @property
    def native_value(self) -> str | None:
        prog = self._programme()
        return prog.title[:255] if prog else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        prog = self._programme()
        if not prog:
            return {}
        return {
            "start": prog.start,
            "end": prog.stop,
            "description": (prog.description or "")[:500] or None,
            "categories": list(prog.categories),
            "live": prog.live,
        }
