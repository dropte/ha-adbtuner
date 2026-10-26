"""The ADBTuner integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ADBTunerClient
from .const import CONF_GUIDE_URL
from .coordinator import ADBTunerCoordinator, GuideCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR, Platform.IMAGE, Platform.SENSOR]


@dataclass
class ADBTunerRuntime:
    coordinator: ADBTunerCoordinator
    guide: GuideCoordinator | None


type ADBTunerConfigEntry = ConfigEntry[ADBTunerRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: ADBTunerConfigEntry) -> bool:
    client = ADBTunerClient(async_get_clientsession(hass), entry.data[CONF_URL])
    coordinator = ADBTunerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    guide = None
    if guide_url := entry.options.get(CONF_GUIDE_URL):
        guide = GuideCoordinator(hass, entry, guide_url)
        # A broken guide shouldn't stop the tuner entities from loading.
        await guide.async_refresh()

    entry.runtime_data = ADBTunerRuntime(coordinator, guide)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ADBTunerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ADBTunerConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
