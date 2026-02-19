"""Config flow for ArtNet DMX Controller."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_TARGET_IP,
    CONF_UNIVERSE,
    DEFAULT_UNIVERSE,
    DOMAIN,
    MAX_UNIVERSE,
)


class ArtNetDMXControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ArtNet DMX Controller."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input
            target_ip = user_input[CONF_TARGET_IP]
            universe = user_input[CONF_UNIVERSE]

            # Basic validation
            if not target_ip:
                errors["base"] = "invalid_ip"
            elif not 0 <= universe <= MAX_UNIVERSE:
                errors["base"] = "invalid_universe"
            else:
                # Create a unique ID based on IP and universe
                await self.async_set_unique_id(f"{target_ip}_{universe}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"ArtNet DMX ({target_ip} U:{universe})",
                    data=user_input,
                )

        # Show the form
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TARGET_IP,
                    default=(user_input or {}).get(CONF_TARGET_IP, ""),
                ): str,
                vol.Required(
                    CONF_UNIVERSE,
                    default=(user_input or {}).get(CONF_UNIVERSE, DEFAULT_UNIVERSE),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=32767)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ArtNetDMXControllerOptionsFlow:
        """Get the options flow for this handler."""
        return ArtNetDMXControllerOptionsFlow(config_entry)


class ArtNetDMXControllerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ArtNet DMX Controller."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
