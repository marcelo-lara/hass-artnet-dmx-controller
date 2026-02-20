import pytest

from custom_components.artnet_dmx_controller.channel_math import (
    absolute_channel,
    clamp_dmx_value,
    label_from_value,
    validate_dmx_value,
    value_from_label,
)


def test_absolute_channel_ok():
    assert absolute_channel(1, 1) == 1
    assert absolute_channel(10, 5) == 14


def test_absolute_channel_out_of_range():
    with pytest.raises(Exception):
        absolute_channel(512, 2)


def test_validate_dmx_value_ok():
    assert validate_dmx_value(0) == 0
    assert validate_dmx_value(255) == 255


def test_validate_dmx_value_invalid():
    with pytest.raises(Exception):
        validate_dmx_value(256)


def test_clamp_dmx_value():
    assert clamp_dmx_value(-5) == 0
    assert clamp_dmx_value(300) == 255
    assert clamp_dmx_value(128) == 128


def test_value_label_map():
    vm = {"0": "Off", "128": "Mid", "255": "Full"}
    assert value_from_label(vm, "Mid") == 128
    assert label_from_value(vm, 255) == "Full"
    assert label_from_value(vm, 1) is None
