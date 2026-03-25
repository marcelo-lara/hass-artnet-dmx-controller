"""Config flow for ArtNet DMX Controller."""

from __future__ import annotations

import ipaddress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_FIXTURE_ID,
    CONF_FIXTURE_TYPE,
    CONF_FIXTURES,
    CONF_NAME,
    CONF_START_CHANNEL,
    CONF_TARGET_IP,
    CONF_UNIVERSE,
    DEFAULT_UNIVERSE,
    DOMAIN,
    MAX_UNIVERSE,
)
from .entry_fixtures import (
    build_fixture_config,
    get_entry_fixtures,
    normalize_entry_data,
    validate_fixture_channels,
    validate_fixture_overlap,
)
from .fixture_mapping import HomeAssistantError, load_fixture_mapping


class ArtNetDMXControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ArtNet DMX Controller."""

    VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            target_ip = user_input[CONF_TARGET_IP]
            universe = user_input[CONF_UNIVERSE]

            try:
                ipaddress.ip_address(target_ip)
            except ValueError:
                errors["base"] = "invalid_ip"
            else:
                if not 0 <= universe <= MAX_UNIVERSE:
                    errors["base"] = "invalid_universe"
                else:
                    await self.async_set_unique_id(f"{target_ip}_{universe}")
                    self._abort_if_unique_id_configured()

                    if not errors:
                        entry_data = {
                            CONF_TARGET_IP: target_ip,
                            CONF_UNIVERSE: int(universe),
                            CONF_FIXTURES: [],
                        }
                        if user_input.get(CONF_NAME):
                            entry_data[CONF_NAME] = user_input[CONF_NAME].strip()
                        return self.async_create_entry(
                            title=f"ArtNet DMX ({target_ip} U:{universe})",
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
        self._editing_fixture_id: str | None = None

    async def async_step_init(self, user_input=None):
        """Present available options actions."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["node_options", "add_fixture", "edit_fixture", "remove_fixture"],
        )

    async def async_step_node_options(self, user_input=None):
        """Manage non-entity options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._entry.options or {}
        data_schema = vol.Schema(
            {
                vol.Optional("default_transition", default=opts.get("default_transition", 0)):
                vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional("expose_scenes", default=opts.get("expose_scenes", True)): bool,
            }
        )

        return self.async_show_form(step_id="node_options", data_schema=data_schema, errors=errors)

    async def async_step_add_fixture(self, user_input=None):
        """Add a fixture to an existing node/universe entry."""
        errors: dict[str, str] = {}
        mapping = self._get_mapping()
        fixture_choices = {k: k for k in mapping.get("fixtures", {}).keys()}

        if user_input is not None:
            fixture_type = user_input[CONF_FIXTURE_TYPE]
            fixture_def = mapping.get("fixtures", {}).get(fixture_type)
            if fixture_def is None:
                errors["base"] = "unknown_fixture_type"
            else:
                fixture = build_fixture_config(
                    fixture_type=fixture_type,
                    start_channel=int(user_input[CONF_START_CHANNEL]),
                    channel_count=int(fixture_def["channel_count"]),
                    name=user_input.get(CONF_NAME),
                )
                try:
                    validate_fixture_channels(fixture)
                    validate_fixture_overlap(get_entry_fixtures(self._entry), fixture)
                except HomeAssistantError as err:
                    if str(err) == "channel_overlap":
                        errors["base"] = "channel_overlap"
                    else:
                        errors["base"] = "invalid_channel_range"

                if not errors:
                    updated_data = normalize_entry_data(self._entry.data)
                    updated_data[CONF_FIXTURES].append(fixture)
                    self.hass.config_entries.async_update_entry(self._entry, data=updated_data)
                    await self.hass.config_entries.async_reload(self._entry.entry_id)
                    return self.async_create_entry(title="", data=self._entry.options)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_FIXTURE_TYPE, default=(user_input or {}).get(CONF_FIXTURE_TYPE)): vol.In(
                    list(fixture_choices.keys())
                ),
                vol.Required(CONF_START_CHANNEL, default=(user_input or {}).get(CONF_START_CHANNEL, 1)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=512)
                ),
                vol.Optional(CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")): str,
            }
        )
        return self.async_show_form(step_id="add_fixture", data_schema=data_schema, errors=errors)

    async def async_step_remove_fixture(self, user_input=None):
        """Remove one fixture from the entry."""
        fixtures = get_entry_fixtures(self._entry)
        if not fixtures:
            return self.async_abort(reason="no_fixtures")

        if user_input is not None:
            fixture_id = user_input[CONF_FIXTURE_ID]
            updated_data = normalize_entry_data(self._entry.data)
            updated_data[CONF_FIXTURES] = [
                fixture for fixture in updated_data[CONF_FIXTURES] if fixture.get(CONF_FIXTURE_ID) != fixture_id
            ]
            self.hass.config_entries.async_update_entry(self._entry, data=updated_data)
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data=self._entry.options)

        fixture_choices = {
            fixture[CONF_FIXTURE_ID]: (
                f"{fixture.get(CONF_NAME) or fixture[CONF_FIXTURE_TYPE]} @ CH {fixture[CONF_START_CHANNEL]}"
            )
            for fixture in fixtures
        }
        data_schema = vol.Schema({vol.Required(CONF_FIXTURE_ID): vol.In(fixture_choices)})
        return self.async_show_form(step_id="remove_fixture", data_schema=data_schema, errors={})

    async def async_step_edit_fixture(self, user_input=None):
        """Select a fixture to edit."""
        fixtures = get_entry_fixtures(self._entry)
        if not fixtures:
            return self.async_abort(reason="no_fixtures")

        if user_input is not None:
            self._editing_fixture_id = user_input[CONF_FIXTURE_ID]
            return await self.async_step_edit_fixture_details()

        fixture_choices = {
            fixture[CONF_FIXTURE_ID]: (
                f"{fixture.get(CONF_NAME) or fixture[CONF_FIXTURE_TYPE]} @ CH {fixture[CONF_START_CHANNEL]}"
            )
            for fixture in fixtures
        }
        data_schema = vol.Schema({vol.Required(CONF_FIXTURE_ID): vol.In(fixture_choices)})
        return self.async_show_form(step_id="edit_fixture", data_schema=data_schema, errors={})

    async def async_step_edit_fixture_details(self, user_input=None):
        """Edit one existing fixture."""
        fixtures = get_entry_fixtures(self._entry)
        if not fixtures:
            return self.async_abort(reason="no_fixtures")

        fixture = next(
            (item for item in fixtures if item.get(CONF_FIXTURE_ID) == self._editing_fixture_id),
            None,
        )
        if fixture is None:
            return self.async_abort(reason="no_fixtures")

        errors: dict[str, str] = {}
        mapping = self._get_mapping()
        fixture_choices = {key: key for key in mapping.get("fixtures", {}).keys()}

        if user_input is not None:
            fixture_type = user_input[CONF_FIXTURE_TYPE]
            fixture_def = mapping.get("fixtures", {}).get(fixture_type)
            if fixture_def is None:
                errors["base"] = "unknown_fixture_type"
            else:
                updated_fixture = build_fixture_config(
                    fixture_type=fixture_type,
                    start_channel=int(user_input[CONF_START_CHANNEL]),
                    channel_count=int(fixture_def["channel_count"]),
                    name=user_input.get(CONF_NAME),
                    fixture_id=fixture[CONF_FIXTURE_ID],
                )
                try:
                    validate_fixture_channels(updated_fixture)
                    validate_fixture_overlap(
                        fixtures,
                        updated_fixture,
                        exclude_fixture_id=fixture[CONF_FIXTURE_ID],
                    )
                except HomeAssistantError as err:
                    if str(err) == "channel_overlap":
                        errors["base"] = "channel_overlap"
                    else:
                        errors["base"] = "invalid_channel_range"

                if not errors:
                    updated_data = normalize_entry_data(self._entry.data)
                    updated_data[CONF_FIXTURES] = [
                        updated_fixture if item.get(CONF_FIXTURE_ID) == fixture[CONF_FIXTURE_ID] else item
                        for item in updated_data[CONF_FIXTURES]
                    ]
                    self.hass.config_entries.async_update_entry(self._entry, data=updated_data)
                    await self.hass.config_entries.async_reload(self._entry.entry_id)
                    return self.async_create_entry(title="", data=self._entry.options)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_FIXTURE_TYPE,
                    default=(user_input or {}).get(CONF_FIXTURE_TYPE, fixture[CONF_FIXTURE_TYPE]),
                ): vol.In(list(fixture_choices.keys())),
                vol.Required(
                    CONF_START_CHANNEL,
                    default=(user_input or {}).get(CONF_START_CHANNEL, fixture[CONF_START_CHANNEL]),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=512)),
                vol.Optional(
                    CONF_NAME,
                    default=(user_input or {}).get(CONF_NAME, fixture.get(CONF_NAME, "")),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="edit_fixture_details",
            data_schema=data_schema,
            errors=errors,
        )

    def _get_mapping(self) -> dict[str, Any]:
        """Load and cache fixture mapping for options steps."""
        if self._mapping is None:
            self._mapping = load_fixture_mapping()
        return self._mapping


async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
