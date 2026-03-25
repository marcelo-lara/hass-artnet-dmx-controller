"""Helpers for fixture-first config entries."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .channel_math import absolute_channel
from .const import (
    CONF_CHANNEL_COUNT,
    CONF_FIXTURE_ID,
    CONF_FIXTURE_TYPE,
    CONF_LOCATION,
    CONF_NAME,
    CONF_START_CHANNEL,
    CONF_TARGET_IP,
    CONF_UNIVERSE,
)
from .fixture_mapping import HomeAssistantError


LEGACY_CONF_FIXTURES = "fixtures"


def build_fixture_entry_data(
    target_ip: str,
    universe: int,
    fixture_type: str,
    start_channel: int,
    channel_count: int,
    name: str | None = None,
    fixture_id: str | None = None,
    location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized fixture-entry data."""
    fixture: dict[str, Any] = {
        CONF_TARGET_IP: str(target_ip),
        CONF_UNIVERSE: int(universe),
        CONF_FIXTURE_ID: fixture_id or uuid4().hex,
        CONF_FIXTURE_TYPE: fixture_type,
        CONF_START_CHANNEL: int(start_channel),
        CONF_CHANNEL_COUNT: int(channel_count),
    }
    if name:
        fixture[CONF_NAME] = name.strip()
    if location is not None:
        fixture[CONF_LOCATION] = deepcopy(location)
    return fixture


def normalize_fixture_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize config-entry data into the fixture-first format."""
    normalized = dict(data)
    normalized[CONF_TARGET_IP] = str(normalized[CONF_TARGET_IP])
    normalized[CONF_UNIVERSE] = int(normalized[CONF_UNIVERSE])
    normalized[CONF_FIXTURE_ID] = str(normalized.get(CONF_FIXTURE_ID) or uuid4().hex)
    normalized[CONF_FIXTURE_TYPE] = str(normalized[CONF_FIXTURE_TYPE])
    normalized[CONF_START_CHANNEL] = int(normalized[CONF_START_CHANNEL])
    normalized[CONF_CHANNEL_COUNT] = int(normalized[CONF_CHANNEL_COUNT])
    name = normalized.get(CONF_NAME)
    if isinstance(name, str):
        name = name.strip()
        if name:
            normalized[CONF_NAME] = name
        else:
            normalized.pop(CONF_NAME, None)
    else:
        normalized.pop(CONF_NAME, None)
    if CONF_LOCATION in normalized:
        normalized[CONF_LOCATION] = deepcopy(normalized[CONF_LOCATION])
    return normalized


def extract_fixture_records(entry_or_data: Any) -> list[dict[str, Any]]:
    """Return fixture records from current or legacy config-entry data."""
    data = entry_or_data.data if hasattr(entry_or_data, "data") else entry_or_data
    if {
        CONF_TARGET_IP,
        CONF_UNIVERSE,
        CONF_FIXTURE_TYPE,
        CONF_START_CHANNEL,
        CONF_CHANNEL_COUNT,
    }.issubset(data):
        return [normalize_fixture_entry_data(data)]

    fixtures = data.get(LEGACY_CONF_FIXTURES)
    if not isinstance(fixtures, list):
        return []

    target_ip = data.get(CONF_TARGET_IP)
    universe = data.get(CONF_UNIVERSE)
    if target_ip is None or universe is None:
        return []

    records: list[dict[str, Any]] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        if not {
            CONF_FIXTURE_TYPE,
            CONF_START_CHANNEL,
            CONF_CHANNEL_COUNT,
        }.issubset(fixture):
            continue
        records.append(
            build_fixture_entry_data(
                target_ip=str(target_ip),
                universe=int(universe),
                fixture_type=str(fixture[CONF_FIXTURE_TYPE]),
                start_channel=int(fixture[CONF_START_CHANNEL]),
                channel_count=int(fixture[CONF_CHANNEL_COUNT]),
                name=fixture.get(CONF_NAME) if isinstance(fixture.get(CONF_NAME), str) else data.get(CONF_NAME),
                fixture_id=fixture.get(CONF_FIXTURE_ID),
                location=fixture.get(CONF_LOCATION),
            )
        )
    return records


def get_fixture_entry(entry_or_data: Any) -> dict[str, Any]:
    """Return one normalized fixture entry from current config-entry data."""
    records = extract_fixture_records(entry_or_data)
    if not records:
        msg = "Fixture entry data is missing required fields"
        raise HomeAssistantError(msg)
    return deepcopy(records[0])


def fixture_label(entry_or_data: Any, fallback: str | None = None) -> str | None:
    """Return display label for a fixture entry."""
    data = entry_or_data.data if hasattr(entry_or_data, "data") else entry_or_data
    return data.get(CONF_NAME) or fallback or data.get(CONF_FIXTURE_TYPE)


def fixture_title(entry_or_data: Any) -> str:
    """Return a Home Assistant config-entry title for a fixture entry."""
    data = entry_or_data.data if hasattr(entry_or_data, "data") else entry_or_data
    label = fixture_label(data) or "DMX Fixture"
    return f"{label} ({data[CONF_TARGET_IP]} U:{data[CONF_UNIVERSE]} CH:{data[CONF_START_CHANNEL]})"


def fixture_channels(entry_or_data: Any) -> list[int]:
    """Return all absolute channels belonging to a fixture entry."""
    data = entry_or_data.data if hasattr(entry_or_data, "data") else entry_or_data
    normalized = normalize_fixture_entry_data(data)
    start_channel = int(normalized[CONF_START_CHANNEL])
    channel_count = int(normalized[CONF_CHANNEL_COUNT])
    return list(range(start_channel, start_channel + channel_count))


def validate_fixture_channels(fixture: dict[str, Any]) -> None:
    """Validate the channel range for one fixture."""
    absolute_channel(int(fixture[CONF_START_CHANNEL]), int(fixture[CONF_CHANNEL_COUNT]))


def validate_fixture_overlap(
    entries: list[Any],
    candidate: dict[str, Any],
    exclude_entry_id: str | None = None,
) -> None:
    """Raise if candidate overlaps any fixture on the same target IP and universe."""
    candidate = normalize_fixture_entry_data(candidate)
    candidate_start = int(candidate[CONF_START_CHANNEL])
    candidate_end = candidate_start + int(candidate[CONF_CHANNEL_COUNT]) - 1
    for entry in entries:
        if hasattr(entry, "entry_id") and entry.entry_id == exclude_entry_id:
            continue
        for fixture in extract_fixture_records(entry):
            if fixture[CONF_TARGET_IP] != candidate[CONF_TARGET_IP]:
                continue
            if int(fixture[CONF_UNIVERSE]) != int(candidate[CONF_UNIVERSE]):
                continue
            start = int(fixture[CONF_START_CHANNEL])
            end = start + int(fixture[CONF_CHANNEL_COUNT]) - 1
            if not (end < candidate_start or candidate_end < start):
                raise HomeAssistantError("channel_overlap")
