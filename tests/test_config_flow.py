import asyncio
from types import SimpleNamespace

import custom_components.artnet_dmx_controller.config_flow as cf_mod
import custom_components.artnet_dmx_controller as integration_init
from custom_components.artnet_dmx_controller.config_flow import (
    ArtNetDMXControllerConfigFlow,
)
from custom_components.artnet_dmx_controller.const import CONF_FIXTURES


def _make_flow(mapping, existing_entries=None):
    flow = ArtNetDMXControllerConfigFlow()

    # Replace module loader to return our mapping
    cf_mod.load_fixture_mapping = lambda: mapping

    # Provide required helper methods used by the flow
    flow._async_current_entries = lambda: existing_entries or []

    async def _set_uid(uid):
        return None

    flow.async_set_unique_id = _set_uid
    flow._abort_if_unique_id_configured = lambda: None

    # Stub out UI/result helpers so tests can observe results
    flow.async_create_entry = lambda title, data: {"title": title, "data": data}
    flow.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}

    return flow


def test_config_flow_happy_path():
    flow = _make_flow({"fixtures": {}})

    user_input = {"target_ip": "192.168.1.100", "universe": 0, "name": "Front Truss"}
    result = asyncio.run(flow.async_step_user(user_input))

    assert result["data"]["target_ip"] == "192.168.1.100"
    assert result["data"]["universe"] == 0
    assert result["data"][CONF_FIXTURES] == []


def test_config_flow_invalid_ip():
    flow = _make_flow({"fixtures": {}})

    user_input = {"target_ip": "not-an-ip", "universe": 0}
    result = asyncio.run(flow.async_step_user(user_input))

    assert result["errors"]["base"] == "invalid_ip"


def test_migrate_legacy_entry_to_fixture_list():
    entry = SimpleNamespace(
        entry_id="legacy-entry",
        version=1,
        data={
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "parcan",
            "start_channel": 10,
            "channel_count": 5,
            "name": "Par Can Left",
        },
    )

    updated = {}

    class FakeConfigEntries:
        def async_update_entry(self, config_entry, data=None, version=None):
            updated["data"] = data
            updated["version"] = version

    hass = SimpleNamespace(config_entries=FakeConfigEntries())

    result = asyncio.run(integration_init.async_migrate_entry(hass, entry))

    assert result is True
    assert updated["version"] == 2
    assert len(updated["data"][CONF_FIXTURES]) == 1
    migrated_fixture = updated["data"][CONF_FIXTURES][0]
    assert migrated_fixture["fixture_type"] == "parcan"
    assert migrated_fixture["start_channel"] == 10


def test_options_add_fixture_detects_overlap():
    mapping = {
        "fixtures": {
            "parcan": {
                "channel_count": 5,
                "channels": [{"name": f"ch{i}", "offset": i, "description": "d"} for i in range(1, 6)],
            }
        }
    }

    cf_mod.load_fixture_mapping = lambda: mapping
    entry = SimpleNamespace(
        entry_id="node-1",
        data={
            "target_ip": "192.168.1.100",
            "universe": 0,
            CONF_FIXTURES: [
                {"id": "fixture-a", "fixture_type": "parcan", "start_channel": 10, "channel_count": 5}
            ],
        },
        options={},
    )

    updated = []

    class FakeConfigEntries:
        def async_update_entry(self, *args, **kwargs):
            updated.append((args, kwargs))

        async def async_reload(self, *args, **kwargs):
            return None

    handler = cf_mod.OptionsFlowHandler(entry)
    handler.hass = SimpleNamespace(config_entries=FakeConfigEntries())
    handler.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}
    handler.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        handler.async_step_add_fixture(
            {"fixture_type": "parcan", "start_channel": 12, "name": "Overlap Fixture"}
        )
    )

    assert result["errors"]["base"] == "channel_overlap"
    assert updated == []


def test_options_add_fixture_appends_fixture():
    mapping = {
        "fixtures": {
            "parcan": {
                "channel_count": 5,
                "channels": [{"name": f"ch{i}", "offset": i, "description": "d"} for i in range(1, 6)],
            }
        }
    }

    cf_mod.load_fixture_mapping = lambda: mapping
    entry = SimpleNamespace(
        entry_id="node-1",
        data={"target_ip": "192.168.1.100", "universe": 0, CONF_FIXTURES: []},
        options={"default_transition": 0},
    )

    updates = {}

    class FakeConfigEntries:
        def async_update_entry(self, config_entry, data=None, version=None):
            updates["data"] = data

        async def async_reload(self, entry_id):
            updates["reloaded"] = entry_id

    handler = cf_mod.OptionsFlowHandler(entry)
    handler.hass = SimpleNamespace(config_entries=FakeConfigEntries())
    handler.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}
    handler.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        handler.async_step_add_fixture(
            {"fixture_type": "parcan", "start_channel": 20, "name": "Par Left"}
        )
    )

    assert result["data"] == entry.options
    assert updates["reloaded"] == "node-1"
    assert len(updates["data"][CONF_FIXTURES]) == 1
    assert updates["data"][CONF_FIXTURES][0]["start_channel"] == 20


def test_options_edit_fixture_updates_fixture():
    mapping = {
        "fixtures": {
            "parcan": {
                "channel_count": 5,
                "channels": [{"name": f"ch{i}", "offset": i, "description": "d"} for i in range(1, 6)],
            },
            "mini": {
                "channel_count": 3,
                "channels": [{"name": f"ch{i}", "offset": i, "description": "d"} for i in range(1, 4)],
            },
        }
    }

    cf_mod.load_fixture_mapping = lambda: mapping
    entry = SimpleNamespace(
        entry_id="node-1",
        data={
            "target_ip": "192.168.1.100",
            "universe": 0,
            CONF_FIXTURES: [
                {"id": "fixture-a", "fixture_type": "parcan", "start_channel": 20, "channel_count": 5}
            ],
        },
        options={"default_transition": 0},
    )

    updates = {}

    class FakeConfigEntries:
        def async_update_entry(self, config_entry, data=None, version=None):
            updates["data"] = data

        async def async_reload(self, entry_id):
            updates["reloaded"] = entry_id

    handler = cf_mod.OptionsFlowHandler(entry)
    handler.hass = SimpleNamespace(config_entries=FakeConfigEntries())
    handler.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}
    handler.async_create_entry = lambda title, data: {"title": title, "data": data}
    handler._editing_fixture_id = "fixture-a"

    result = asyncio.run(
        handler.async_step_edit_fixture_details(
            {"fixture_type": "mini", "start_channel": 30, "name": "Edited Fixture"}
        )
    )

    assert result["data"] == entry.options
    assert updates["reloaded"] == "node-1"
    assert len(updates["data"][CONF_FIXTURES]) == 1
    assert updates["data"][CONF_FIXTURES][0]["fixture_type"] == "mini"
    assert updates["data"][CONF_FIXTURES][0]["start_channel"] == 30
    assert updates["data"][CONF_FIXTURES][0]["name"] == "Edited Fixture"
