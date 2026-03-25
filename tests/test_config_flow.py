import asyncio
from types import SimpleNamespace

import custom_components.artnet_dmx_controller as integration_init
import custom_components.artnet_dmx_controller.config_flow as cf_mod
from custom_components.artnet_dmx_controller.config_flow import ArtNetDMXControllerConfigFlow, OptionsFlowHandler


def _mapping() -> dict:
    return {
        "fixtures": {
            "parcan_rgb_gen": {
                "channel_count": 5,
                "channels": [{"name": f"ch{i}", "offset": i, "description": "d"} for i in range(1, 6)],
            },
            "mini": {
                "channel_count": 3,
                "channels": [{"name": f"ch{i}", "offset": i, "description": "d"} for i in range(1, 4)],
            },
        }
    }


def _make_flow(mapping, existing_entries=None):
    flow = ArtNetDMXControllerConfigFlow()
    cf_mod.load_fixture_mapping = lambda: mapping
    flow._async_current_entries = lambda: existing_entries or []

    async def _set_uid(_uid):
        return None

    flow.async_set_unique_id = _set_uid
    flow._abort_if_unique_id_configured = lambda: None
    flow.async_create_entry = lambda title, data: {"title": title, "data": data}
    flow.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}
    return flow


def test_config_flow_happy_path():
    flow = _make_flow(_mapping())

    result = asyncio.run(
        flow.async_step_user(
            {
                "target_ip": "192.168.1.100",
                "universe": 0,
                "fixture_type": "parcan_rgb_gen",
                "start_channel": 10,
                "name": "Front Wash",
            }
        )
    )

    assert result["data"]["target_ip"] == "192.168.1.100"
    assert result["data"]["universe"] == 0
    assert result["data"]["fixture_type"] == "parcan_rgb_gen"
    assert result["data"]["start_channel"] == 10
    assert result["data"]["channel_count"] == 5


def test_config_flow_invalid_ip():
    flow = _make_flow(_mapping())

    result = asyncio.run(
        flow.async_step_user(
            {
                "target_ip": "not-an-ip",
                "universe": 0,
                "fixture_type": "parcan_rgb_gen",
                "start_channel": 10,
            }
        )
    )

    assert result["errors"]["base"] == "invalid_ip"


def test_config_flow_detects_overlap_on_same_target_and_universe():
    existing_entries = [
        SimpleNamespace(
            entry_id="existing",
            data={
                "id": "fixture-1",
                "target_ip": "192.168.1.100",
                "universe": 0,
                "fixture_type": "parcan_rgb_gen",
                "start_channel": 10,
                "channel_count": 5,
            },
        )
    ]
    flow = _make_flow(_mapping(), existing_entries=existing_entries)

    result = asyncio.run(
        flow.async_step_user(
            {
                "target_ip": "192.168.1.100",
                "universe": 0,
                "fixture_type": "mini",
                "start_channel": 12,
            }
        )
    )

    assert result["errors"]["base"] == "channel_overlap"


def test_migrate_legacy_entry_to_fixture_first():
    entry = SimpleNamespace(
        entry_id="legacy-entry",
        version=1,
        data={
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "parcan_rgb_gen",
            "start_channel": 10,
            "channel_count": 5,
            "name": "Par Can Left",
        },
    )

    updated = {}

    class FakeConfigEntries:
        def async_update_entry(self, config_entry, data=None, title=None, version=None):
            updated["data"] = data
            updated["title"] = title
            updated["version"] = version

    hass = SimpleNamespace(config_entries=FakeConfigEntries())

    result = asyncio.run(integration_init.async_migrate_entry(hass, entry))

    assert result is True
    assert updated["version"] == 3
    assert updated["data"]["fixture_type"] == "parcan_rgb_gen"
    assert updated["data"]["start_channel"] == 10


def test_migrate_multi_fixture_legacy_entry_fails_cleanly():
    entry = SimpleNamespace(
        entry_id="legacy-multi",
        version=2,
        data={
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixtures": [
                {"id": "fixture-a", "fixture_type": "parcan_rgb_gen", "start_channel": 1, "channel_count": 5},
                {"id": "fixture-b", "fixture_type": "parcan_rgb_gen", "start_channel": 10, "channel_count": 5},
            ],
        },
    )

    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=lambda *args, **kwargs: None))

    result = asyncio.run(integration_init.async_migrate_entry(hass, entry))

    assert result is False


def test_options_fixture_update_detects_overlap():
    cf_mod.load_fixture_mapping = lambda: _mapping()
    entry = SimpleNamespace(
        entry_id="fixture-entry",
        data={
            "id": "fixture-a",
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "parcan_rgb_gen",
            "start_channel": 20,
            "channel_count": 5,
        },
        options={},
    )

    other_entry = SimpleNamespace(
        entry_id="other-entry",
        data={
            "id": "fixture-b",
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "parcan_rgb_gen",
            "start_channel": 10,
            "channel_count": 5,
        },
    )
    updates = []

    class FakeConfigEntries:
        def async_update_entry(self, *args, **kwargs):
            updates.append((args, kwargs))

        async def async_reload(self, *args, **kwargs):
            return None

        def async_entries(self, domain):
            assert domain == "artnet_dmx_controller"
            return [entry, other_entry]

    handler = OptionsFlowHandler(entry)
    handler.hass = SimpleNamespace(config_entries=FakeConfigEntries())
    handler.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}
    handler.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        handler.async_step_fixture_options(
            {
                "target_ip": "192.168.1.100",
                "universe": 0,
                "fixture_type": "mini",
                "start_channel": 12,
                "name": "Overlap Fixture",
            }
        )
    )

    assert result["errors"]["base"] == "channel_overlap"
    assert updates == []


def test_options_fixture_update_rewrites_entry():
    cf_mod.load_fixture_mapping = lambda: _mapping()
    entry = SimpleNamespace(
        entry_id="fixture-entry",
        data={
            "id": "fixture-a",
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "parcan_rgb_gen",
            "start_channel": 20,
            "channel_count": 5,
        },
        options={"default_transition": 0},
    )
    updates = {}

    class FakeConfigEntries:
        def async_update_entry(self, config_entry, data=None, title=None, version=None):
            updates["data"] = data
            updates["title"] = title

        async def async_reload(self, entry_id):
            updates["reloaded"] = entry_id

        def async_entries(self, domain):
            assert domain == "artnet_dmx_controller"
            return [entry]

    handler = OptionsFlowHandler(entry)
    handler.hass = SimpleNamespace(config_entries=FakeConfigEntries())
    handler.async_show_form = lambda step_id, data_schema=None, errors=None: {"step_id": step_id, "errors": errors}
    handler.async_create_entry = lambda title, data: {"title": title, "data": data}

    result = asyncio.run(
        handler.async_step_fixture_options(
            {
                "target_ip": "192.168.1.101",
                "universe": 1,
                "fixture_type": "mini",
                "start_channel": 30,
                "name": "Edited Fixture",
            }
        )
    )

    assert result["data"] == entry.options
    assert updates["reloaded"] == "fixture-entry"
    assert updates["data"]["target_ip"] == "192.168.1.101"
    assert updates["data"]["universe"] == 1
    assert updates["data"]["fixture_type"] == "mini"
    assert updates["data"]["start_channel"] == 30
    assert updates["data"]["channel_count"] == 3
