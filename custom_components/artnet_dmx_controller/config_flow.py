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
from .fixture_mapping import load_fixture_mapping, HomeAssistantError
from .channel_math import absolute_channel


class ArtNetDMXControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ArtNet DMX Controller."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # Load fixture mapping for fixture type choices; non-fatal if missing
        fixture_choices = {}
        try:
            mapping = load_fixture_mapping()
            fixture_choices = {k: k for k in mapping.get("fixtures", {}).keys()}
        except HomeAssistantError:
            # Mapping not available — present no fixture choices and allow only controller config
            mapping = None

        if user_input is not None:
            # Validate the input
            target_ip = user_input[CONF_TARGET_IP]
            universe = user_input[CONF_UNIVERSE]
            fixture_type = user_input.get("fixture_type")
            start_channel = user_input.get("start_channel")

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
                    # Validate fixture fields if provided
                    if fixture_type is None or start_channel is None:
                        errors["base"] = "missing_fixture"
                    else:
                        # Validate fixture_type is known
                        if mapping is None or fixture_type not in mapping.get("fixtures", {}):
                            errors["base"] = "unknown_fixture_type"
                        else:
                            channel_count = mapping["fixtures"][fixture_type]["channel_count"]
                            try:
                                absolute_channel(start_channel, channel_count)
                            except HomeAssistantError:
                                errors["base"] = "invalid_channel_range"

                    # Check overlap with existing config entries that include start/channel_count
                    if not errors:
                        for entry in self._async_current_entries():
                            ed = entry.data
                            if "start_channel" in ed and "channel_count" in ed:
                                s1 = ed["start_channel"]
                                e1 = s1 + ed["channel_count"] - 1
                                s2 = start_channel
                                e2 = start_channel + channel_count - 1
                                if not (e1 < s2 or e2 < s1):
                                    errors["base"] = "channel_overlap"

                    # Create a unique ID based on IP and universe
                    await self.async_set_unique_id(f"{target_ip}_{universe}")
                    self._abort_if_unique_id_configured()

                    if errors:
                        # fall through to show form with errors
                        pass
                    else:
                        # Persist fixture fields into the entry data
                        entry_data = dict(user_input)
                        # ensure start_channel, fixture_type and channel_count are saved
                        entry_data["start_channel"] = int(start_channel)
                        entry_data["fixture_type"] = fixture_type
                        entry_data["channel_count"] = int(channel_count)
                        return self.async_create_entry(
                            title=f"ArtNet DMX ({target_ip} U:{universe})",
                            data=entry_data,
                        )

        # Build form including fixture fields if mapping available
        schema_fields = {
            vol.Required(
                CONF_TARGET_IP,
                default=(user_input or {}).get(CONF_TARGET_IP, ""),
            ): str,
            vol.Required(
                CONF_UNIVERSE,
                default=(user_input or {}).get(CONF_UNIVERSE, DEFAULT_UNIVERSE),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_UNIVERSE)),
        }

        if fixture_choices:
            schema_fields[vol.Required("fixture_type", default=(user_input or {}).get("fixture_type"))] = vol.In(
                list(fixture_choices.keys())
            )
            schema_fields[vol.Required("start_channel", default=(user_input or {}).get("start_channel"))] = vol.All(
                vol.Coerce(int), vol.Range(min=1, max=512)
            )
            schema_fields[vol.Optional("name", default=(user_input or {}).get("name"))] = str

        data_schema = vol.Schema(schema_fields)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
