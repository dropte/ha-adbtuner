"""Config flow for ADBTuner."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ADBTunerClient, ADBTunerError
from .const import CONF_GUIDE_URL, DOMAIN


class ADBTunerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up an ADBTuner server."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            await self.async_set_unique_id(url.lower())
            self._abort_if_unique_id_configured()
            client = ADBTunerClient(async_get_clientsession(self.hass), url)
            try:
                info = await client.get_server_info()
            except ADBTunerError:
                errors["base"] = "cannot_connect"
            else:
                options = {}
                if guide := user_input.get(CONF_GUIDE_URL, "").strip():
                    options[CONF_GUIDE_URL] = guide
                return self.async_create_entry(
                    title="ADBTuner",
                    data={CONF_URL: url},
                    options=options,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default="http://"): str,
                    vol.Optional(CONF_GUIDE_URL, default=""): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ADBTunerOptionsFlow()


class ADBTunerOptionsFlow(OptionsFlow):
    """Change the guide URL."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            guide = user_input.get(CONF_GUIDE_URL, "").strip()
            return self.async_create_entry(data={CONF_GUIDE_URL: guide} if guide else {})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_GUIDE_URL, default=self.config_entry.options.get(CONF_GUIDE_URL, "")): str}
            ),
        )
