"""Config flow for ArtNet DMX Controller."""

from __future__ import annotations

import ipaddress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries

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

            # Validate IP address format
            try:
                ipaddress.ip_address(target_ip)
            except ValueError:
                errors["base"] = "invalid_ip"
            else:
                # Validate universe range
                if not 0 <= universe <= MAX_UNIVERSE:
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
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_UNIVERSE)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
