"""Config flow for ArtNet DMX Controller."""

from __future__ import annotations

import ipaddress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_FIXTURE_TYPE,
    CONF_NAME,
    CONF_START_CHANNEL,
    CONF_TARGET_IP,
    CONF_UNIVERSE,
    DEFAULT_UNIVERSE,
    DOMAIN,
    MAX_UNIVERSE,
)
from .entry_fixtures import (
    build_fixture_entry_data,
    fixture_title,
    get_fixture_entry,
    normalize_fixture_entry_data,
    validate_fixture_channels,
    validate_fixture_overlap,
)
from .fixture_mapping import HomeAssistantError, load_fixture_mapping


class ArtNetDMXControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ArtNet DMX Controller."""

    VERSION = 3

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        mapping = _load_mapping()
        fixture_choices = {key: key for key in mapping.get("fixtures", {}).keys()}

        if user_input is not None:
            target_ip = user_input[CONF_TARGET_IP]
            universe = user_input[CONF_UNIVERSE]
            fixture_type = user_input[CONF_FIXTURE_TYPE]

            try:
                ipaddress.ip_address(target_ip)
            except ValueError:
                errors["base"] = "invalid_ip"
            else:
                if not 0 <= universe <= MAX_UNIVERSE:
                    errors["base"] = "invalid_universe"
                else:
                    fixture_def = mapping.get("fixtures", {}).get(fixture_type)
                    if fixture_def is None:
                        errors["base"] = "unknown_fixture_type"
                    else:
                        entry_data = build_fixture_entry_data(
                            target_ip=target_ip,
                            universe=int(universe),
                            fixture_type=fixture_type,
                            start_channel=int(user_input[CONF_START_CHANNEL]),
                            channel_count=int(fixture_def["channel_count"]),
                            name=user_input.get(CONF_NAME),
                        )
                        try:
                            validate_fixture_channels(entry_data)
                            validate_fixture_overlap(self._async_current_entries(), entry_data)
                        except HomeAssistantError as err:
                            if str(err) == "channel_overlap":
                                errors["base"] = "channel_overlap"
                            else:
                                errors["base"] = "invalid_channel_range"

                    if not errors:
                        await self.async_set_unique_id(entry_data["id"])
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=fixture_title(entry_data),
                            data=entry_data,
                        )

        schema_fields = {
            vol.Required(
                CONF_TARGET_IP,
                default=(user_input or {}).get(CONF_TARGET_IP, ""),
            ): str,
            vol.Required(
                CONF_UNIVERSE,
                default=(user_input or {}).get(CONF_UNIVERSE, DEFAULT_UNIVERSE),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_UNIVERSE)),
            vol.Required(
                CONF_FIXTURE_TYPE,
                default=(user_input or {}).get(CONF_FIXTURE_TYPE),
            ): vol.In(list(fixture_choices.keys())),
            vol.Required(
                CONF_START_CHANNEL,
                default=(user_input or {}).get(CONF_START_CHANNEL, 1),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=512)),
            vol.Optional(CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")): str,
        }

        data_schema = vol.Schema(schema_fields)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for ArtNet DMX Controller config entries."""

    def __init__(self, config_entry):
        self._entry = config_entry
        self.handler = config_entry.entry_id
        self._mapping = None

    async def async_step_init(self, user_input=None):
        """Present available options actions."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["runtime_options", "fixture_options"],
        )

    async def async_step_runtime_options(self, user_input=None):
        """Manage non-entity options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._entry.options or {}
        data_schema = vol.Schema(
            {
                vol.Optional("default_transition", default=opts.get("default_transition", 0)):
                vol.All(vol.Coerce(int), vol.Range(min=0)),
            }
        )

        return self.async_show_form(step_id="runtime_options", data_schema=data_schema, errors=errors)

    async def async_step_fixture_options(self, user_input=None):
        """Edit the current fixture entry."""
        errors: dict[str, str] = {}
        mapping = self._get_mapping()
        fixture_choices = {k: k for k in mapping.get("fixtures", {}).keys()}
        fixture = get_fixture_entry(self._entry)

        if user_input is not None:
            fixture_type = user_input[CONF_FIXTURE_TYPE]
            fixture_def = mapping.get("fixtures", {}).get(fixture_type)
            if fixture_def is None:
                errors["base"] = "unknown_fixture_type"
            else:
                updated_entry = build_fixture_entry_data(
                    target_ip=user_input[CONF_TARGET_IP],
                    universe=int(user_input[CONF_UNIVERSE]),
                    fixture_type=fixture_type,
                    start_channel=int(user_input[CONF_START_CHANNEL]),
                    channel_count=int(fixture_def["channel_count"]),
                    name=user_input.get(CONF_NAME),
                    fixture_id=fixture["id"],
                    location=fixture.get("location"),
                )
                try:
                    ipaddress.ip_address(updated_entry[CONF_TARGET_IP])
                    validate_fixture_channels(updated_entry)
                    validate_fixture_overlap(
                        self.hass.config_entries.async_entries(DOMAIN),
                        updated_entry,
                        exclude_entry_id=self._entry.entry_id,
                    )
                except HomeAssistantError as err:
                    if str(err) == "channel_overlap":
                        errors["base"] = "channel_overlap"
                    else:
                        errors["base"] = "invalid_channel_range"
                except ValueError:
                    errors["base"] = "invalid_ip"

                if not errors:
                    updated_data = normalize_fixture_entry_data(updated_entry)
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data=updated_data,
                        title=fixture_title(updated_data),
                    )
                    await self.hass.config_entries.async_reload(self._entry.entry_id)
                    return self.async_create_entry(title="", data=self._entry.options)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TARGET_IP,
                    default=(user_input or {}).get(CONF_TARGET_IP, fixture[CONF_TARGET_IP]),
                ): str,
                vol.Required(
                    CONF_UNIVERSE,
                    default=(user_input or {}).get(CONF_UNIVERSE, fixture[CONF_UNIVERSE]),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_UNIVERSE)),
                vol.Required(
                    CONF_FIXTURE_TYPE,
                    default=(user_input or {}).get(CONF_FIXTURE_TYPE, fixture[CONF_FIXTURE_TYPE]),
                ): vol.In(
                    list(fixture_choices.keys())
                ),
                vol.Required(
                    CONF_START_CHANNEL,
                    default=(user_input or {}).get(CONF_START_CHANNEL, fixture[CONF_START_CHANNEL]),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=512)
                ),
                vol.Optional(
                    CONF_NAME,
                    default=(user_input or {}).get(CONF_NAME, fixture.get(CONF_NAME, "")),
                ): str,
            }
        )
        return self.async_show_form(step_id="fixture_options", data_schema=data_schema, errors=errors)

    def _get_mapping(self) -> dict[str, Any]:
        """Load and cache fixture mapping for options steps."""
        if self._mapping is None:
            self._mapping = load_fixture_mapping()
        return self._mapping


def _load_mapping() -> dict[str, Any]:
    """Load fixture mapping for the config flow."""
    return load_fixture_mapping()


async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
