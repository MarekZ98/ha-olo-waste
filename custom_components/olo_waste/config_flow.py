"""Config flow: type a street, pick the exact OLO address."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.loader import async_get_integration

from .api import OloApiError, OloClient
from .const import CONF_ADDRESS, DOMAIN, USER_AGENT_FORMAT

_LOGGER = logging.getLogger(__name__)

CONF_STREET = "street"


class OloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: search, then choose."""

    VERSION = 1

    def __init__(self) -> None:
        self._hits: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the street and number, then search OLO."""
        errors: dict[str, str] = {}
        if user_input is not None:
            version = (await async_get_integration(self.hass, DOMAIN)).version
            client = OloClient(async_get_clientsession(self.hass), USER_AGENT_FORMAT.format(version=version))
            try:
                hits = await client.search(user_input[CONF_STREET].strip())
            except (OloApiError, aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("OLO search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if hits:
                    self._hits = hits
                    return await self.async_step_address()
                errors["base"] = "no_address"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_STREET): str}),
            errors=errors,
        )

    async def async_step_address(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user pick one of the OLO addresses."""
        if user_input is not None:
            address: str = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=address, data={CONF_ADDRESS: address})
        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(options=self._hits, mode=SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
        )
