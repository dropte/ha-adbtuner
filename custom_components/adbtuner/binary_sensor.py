"""Binary sensors for ADBTuner."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ADBTunerConfigEntry
from .coordinator import ADBTunerCoordinator
from .entity import ADBTunerTunerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ADBTunerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for tuner_id in coordinator.data.tuners
        for entity in (
            TunerInUseSensor(coordinator, tuner_id),
            TunerDeviceConnectedSensor(coordinator, tuner_id),
            TunerStreamConnectedSensor(coordinator, tuner_id),
        )
    )


class TunerInUseSensor(ADBTunerTunerEntity, BinarySensorEntity):
    """On while ADBTuner holds the tuner (tuning, streaming or maintenance)."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "in_use")

    @property
    def is_on(self) -> bool:
        return self.lock is not None


class TunerDeviceConnectedSensor(ADBTunerTunerEntity, BinarySensorEntity):
    """ADBTuner can talk to the streaming device over ADB."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "device_connected")

    @property
    def is_on(self) -> bool | None:
        meta = self.coordinator.data.metadata.get(self.tuner_id)
        if meta is None:
            return None
        # ADBTuner only reports an Android version once it has an ADB connection.
        return meta.get("version") is not None


class TunerStreamConnectedSensor(ADBTunerTunerEntity, BinarySensorEntity):
    """ADBTuner can reach the tuner's streaming endpoint (HDMI encoder)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "stream_connected")

    @property
    def is_on(self) -> bool | None:
        meta = self.coordinator.data.metadata.get(self.tuner_id)
        return None if meta is None else bool(meta.get("endpoint_connected_successfully"))
