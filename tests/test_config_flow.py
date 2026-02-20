import asyncio
from types import SimpleNamespace

import custom_components.artnet_dmx_controller.config_flow as cf_mod
from custom_components.artnet_dmx_controller.config_flow import ArtNetDMXControllerConfigFlow


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
    mapping = {
        "fixtures": {
            "parcan": {"channel_count": 5, "channels": [{"name": "dim", "offset": 1, "description": "d"}] * 5}
        }
    }
    flow = _make_flow(mapping)

    user_input = {"target_ip": "192.168.1.100", "universe": 0, "fixture_type": "parcan", "start_channel": 10}
    result = asyncio.run(flow.async_step_user(user_input))

    assert result["data"]["fixture_type"] == "parcan"
    assert result["data"]["channel_count"] == 5


def test_config_flow_unknown_fixture():
    mapping = {"fixtures": {}}
    flow = _make_flow(mapping)

    user_input = {"target_ip": "192.168.1.100", "universe": 0, "fixture_type": "unknown", "start_channel": 1}
    result = asyncio.run(flow.async_step_user(user_input))

    assert result["errors"]["base"] == "unknown_fixture_type"


def test_config_flow_invalid_channel():
    # channel_count 5 but start at 510 -> exceeds 512
    mapping = {"fixtures": {"big": {"channel_count": 5, "channels": [{"name": "a", "offset": i + 1, "description": "d"} for i in range(5)]}}}
    flow = _make_flow(mapping)

    user_input = {"target_ip": "192.168.1.100", "universe": 0, "fixture_type": "big", "start_channel": 510}
    result = asyncio.run(flow.async_step_user(user_input))

    assert result["errors"]["base"] == "invalid_channel_range"


def test_config_flow_overlap():
    mapping = {"fixtures": {"parcan": {"channel_count": 5, "channels": [{"name": "a", "offset": i + 1, "description": "d"} for i in range(5)]}}}

    # existing entry occupies channels 12..16
    existing_entry = SimpleNamespace(entry_id="e1", data={"start_channel": 12, "channel_count": 5})
    flow = _make_flow(mapping, existing_entries=[existing_entry])

    # new fixture at start 14 (14..18) overlaps
    user_input = {"target_ip": "192.168.1.100", "universe": 0, "fixture_type": "parcan", "start_channel": 14}
    result = asyncio.run(flow.async_step_user(user_input))

    assert result["errors"]["base"] == "channel_overlap"
