import json
import os
import tempfile

from custom_components.artnet_dmx_controller.fixture_mapping import (
    load_fixture_mapping,
    HomeAssistantError,
    clear_fixture_mapping_cache,
)


def _write_tmp(data: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


def test_valid_mapping_loads():
    data = {
        "schema_version": 1,
        "fixtures": {
            "test_fixture": {
                "fixture_specie": "parcan",
                "channel_count": 2,
                "channels": [
                    {"name": "dim", "offset": 1, "description": "Dimmer"},
                    {"name": "strobe", "offset": 2, "description": "Strobe", "hidden_by_default": True},
                ],
            }
        },
    }
    path = _write_tmp(json.dumps(data))
    try:
        mapping = load_fixture_mapping(path)
        assert "test_fixture" in mapping["fixtures"]
        assert mapping["fixtures"]["test_fixture"]["channel_count"] == 2
    finally:
        os.remove(path)


def test_missing_file_raises():
    try:
        load_fixture_mapping("/nonexistent/path/does_not_exist.json")
    except HomeAssistantError as err:
        assert "not found" in str(err).lower()


def test_malformed_json_raises():
    path = _write_tmp("{ not valid json }")
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for malformed json"
        except HomeAssistantError as err:
            assert "malformed json" in str(err).lower()
    finally:
        os.remove(path)


def test_missing_required_keys_raises():
    data = {"fixtures": {"bad": {"fixture_specie": "x"}}}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for missing keys"
        except HomeAssistantError as err:
            assert "missing required 'channel_count'" in str(err).lower()
    finally:
        os.remove(path)


def test_top_level_not_object_raises():
    path = _write_tmp("[]")
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for top-level non-object"
        except HomeAssistantError as err:
            assert "must be a json object" in str(err).lower()
    finally:
        os.remove(path)


def test_invalid_fixtures_type_raises():
    data = {"fixtures": []}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for invalid fixtures type"
        except HomeAssistantError as err:
            assert "missing or invalid 'fixtures' object" in str(err).lower()
    finally:
        os.remove(path)


def test_fixture_definition_not_object_raises():
    data = {"fixtures": {"bad": "not-an-object"}}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for fixture definition not object"
        except HomeAssistantError as err:
            assert "definition must be an object" in str(err).lower()
    finally:
        os.remove(path)


def test_missing_fixture_specie_raises():
    data = {"fixtures": {"bad": {"channel_count": 1, "channels": []}}}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for missing fixture_specie"
        except HomeAssistantError as err:
            assert "missing required 'fixture_specie'" in str(err).lower()
    finally:
        os.remove(path)


def test_invalid_channel_count_raises():
    # zero channel_count
    data = {"fixtures": {"bad": {"fixture_specie": "x", "channel_count": 0, "channels": []}}}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for invalid channel_count"
        except HomeAssistantError as err:
            assert "invalid 'channel_count'" in str(err).lower()
    finally:
        os.remove(path)


def test_missing_channels_raises():
    data = {"fixtures": {"bad": {"fixture_specie": "x", "channel_count": 1}}}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for missing channels"
        except HomeAssistantError as err:
            assert "missing required 'channels'" in str(err).lower()
    finally:
        os.remove(path)


def test_channels_not_array_raises():
    data = {"fixtures": {"bad": {"fixture_specie": "x", "channel_count": 1, "channels": {}}}}
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for channels not array"
        except HomeAssistantError as err:
            assert "'channels' must be an array" in str(err).lower()
    finally:
        os.remove(path)


def test_channel_not_object_raises():
    data = {
        "fixtures": {
            "bad": {"fixture_specie": "x", "channel_count": 1, "channels": ["not-a-dict"]}
        }
    }
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for channel not object"
        except HomeAssistantError as err:
            assert "channel at index 0 must be an object" in str(err).lower()
    finally:
        os.remove(path)


def test_channel_missing_required_field_raises():
    data = {
        "fixtures": {
            "bad": {
                "fixture_specie": "x",
                "channel_count": 1,
                "channels": [{"offset": 1, "description": "d"}],
            }
        }
    }
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for channel missing name"
        except HomeAssistantError as err:
            assert "missing required 'name'" in str(err).lower()
    finally:
        os.remove(path)


def test_channel_invalid_offset_raises():
    data = {
        "fixtures": {
            "bad": {
                "fixture_specie": "x",
                "channel_count": 2,
                "channels": [{"name": "n", "offset": 3, "description": "d"}],
            }
        }
    }
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for invalid offset"
        except HomeAssistantError as err:
            assert "has invalid offset" in str(err).lower()
    finally:
        os.remove(path)


def test_duplicate_channel_offset_raises():
    data = {
        "fixtures": {
            "bad": {
                "fixture_specie": "x",
                "channel_count": 2,
                "channels": [
                    {"name": "a", "offset": 1, "description": "d"},
                    {"name": "b", "offset": 1, "description": "d"},
                ],
            }
        }
    }
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for duplicate offset"
        except HomeAssistantError as err:
            assert "duplicate channel offset" in str(err).lower()
    finally:
        os.remove(path)


def test_value_map_not_object_raises():
    data = {
        "fixtures": {
            "bad": {
                "fixture_specie": "x",
                "channel_count": 1,
                "channels": [
                    {"name": "a", "offset": 1, "description": "d", "value_map": [1, 2]}
                ],
            }
        }
    }
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for non-object value_map"
        except HomeAssistantError as err:
            assert "'value_map' must be an object" in str(err).lower()
    finally:
        os.remove(path)


def test_hidden_by_default_not_boolean_raises():
    data = {
        "fixtures": {
            "bad": {
                "fixture_specie": "x",
                "channel_count": 1,
                "channels": [
                    {"name": "a", "offset": 1, "description": "d", "hidden_by_default": "yes"}
                ],
            }
        }
    }
    path = _write_tmp(json.dumps(data))
    try:
        try:
            load_fixture_mapping(path)
            assert False, "Expected HomeAssistantError for non-boolean hidden_by_default"
        except HomeAssistantError as err:
            assert "'hidden_by_default' must be boolean" in str(err).lower()
    finally:
        os.remove(path)


def test_load_uses_cache():
    # create initial mapping A
    data_a = {
        "fixtures": {
            "one": {
                "fixture_specie": "x",
                "channel_count": 1,
                "channels": [{"name": "a", "offset": 1, "description": "d"}],
            }
        }
    }
    data_b = {
        "fixtures": {
            "two": {
                "fixture_specie": "x",
                "channel_count": 1,
                "channels": [{"name": "b", "offset": 1, "description": "d"}],
            }
        }
    }
    path = _write_tmp(json.dumps(data_a))
    try:
        clear_fixture_mapping_cache()
        m1 = load_fixture_mapping(path)
        assert "one" in m1["fixtures"]

        # overwrite file with data_b
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data_b))

        # without clearing cache, loader should still return cached mapping
        m2 = load_fixture_mapping(path)
        assert "one" in m2["fixtures"] and "two" not in m2["fixtures"]

        # clear cache and read again -> should get data_b
        clear_fixture_mapping_cache()
        m3 = load_fixture_mapping(path)
        assert "two" in m3["fixtures"] and "one" not in m3["fixtures"]
    finally:
        clear_fixture_mapping_cache()
        os.remove(path)
