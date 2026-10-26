"""The ADBTuner integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import ADBTunerClient
from .const import CONF_GUIDE_URL, DOMAIN
from .coordinator import ADBTunerCoordinator, GuideCoordinator
from .holder import DEFAULT_HOLD, StreamHolder

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.IMAGE,
    Platform.SELECT,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_DEVICE_ID = "device_id"
ATTR_CHANNEL = "channel"
ATTR_DURATION = "duration"

TUNE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CHANNEL): cv.string,
        vol.Optional(ATTR_DURATION, default=DEFAULT_HOLD): cv.positive_time_period,
    }
)
STOP_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


@dataclass
class ADBTunerRuntime:
    coordinator: ADBTunerCoordinator
    guide: GuideCoordinator | None
    holder: StreamHolder


type ADBTunerConfigEntry = ConfigEntry[ADBTunerRuntime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the tune/stop actions."""

    def _resolve(call: ServiceCall) -> tuple[ADBTunerRuntime, int]:
        device = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
        if device:
            for domain, ident in device.identifiers:
                if domain != DOMAIN or "_" not in ident:
                    continue
                entry_id, tuner_id = ident.rsplit("_", 1)
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry and entry.state is ConfigEntryState.LOADED:
                    return entry.runtime_data, int(tuner_id)
        raise ServiceValidationError("Pick an ADBTuner tuner device")

    async def tune(call: ServiceCall) -> None:
        runtime, tuner_id = _resolve(call)
        channel = runtime.coordinator.find_channel(call.data[ATTR_CHANNEL])
        if channel is None:
            raise ServiceValidationError(f"No ADBTuner channel matches '{call.data[ATTR_CHANNEL]}'")
        await runtime.holder.start(tuner_id, channel["id"], call.data[ATTR_DURATION])

    async def stop(call: ServiceCall) -> None:
        runtime, tuner_id = _resolve(call)
        await runtime.holder.stop(tuner_id)

    hass.services.async_register(DOMAIN, "tune", tune, schema=TUNE_SCHEMA)
    hass.services.async_register(DOMAIN, "stop", stop, schema=STOP_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ADBTunerConfigEntry) -> bool:
    client = ADBTunerClient(async_get_clientsession(hass), entry.data[CONF_URL])
    coordinator = ADBTunerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    guide = None
    if guide_url := entry.options.get(CONF_GUIDE_URL):
        guide = GuideCoordinator(hass, entry, guide_url)
        # A broken guide shouldn't stop the tuner entities from loading.
        await guide.async_refresh()

    entry.runtime_data = ADBTunerRuntime(coordinator, guide, StreamHolder(hass, client.base_url))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ADBTunerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ADBTunerConfigEntry) -> bool:
    await entry.runtime_data.holder.stop_all()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
