"""
Custom integration for ArtNet DMX Controller with Home Assistant.

For more details about this integration, please refer to
https://github.com/marcelo-lara/hass-artnet-dmx-controller
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

from .artnet import ArtNetDMXHelper
from .const import (
    CONF_FIXTURE_TYPE,
    CONF_NAME,
    CONF_TARGET_IP,
    CONF_UNIVERSE,
    DATA_ENTRY_DATA,
    DATA_ENTRY_HELPER_KEYS,
    DATA_HELPER_LOCK,
    DATA_HELPER_REFCOUNTS,
    DATA_SHARED_HELPERS,
    DOMAIN,
    LOGGER,
)
from .entry_fixtures import extract_fixture_records, fixture_label, fixture_title, get_fixture_entry

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SELECT,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entries to the fixture-first format."""
    if entry.version >= 3:
        return True

    fixture_records = extract_fixture_records(entry.data)
    if entry.version in (1, 2) and len(fixture_records) == 1:
        updated_data = fixture_records[0]
        hass.config_entries.async_update_entry(
            entry,
            data=updated_data,
            title=fixture_title(updated_data),
            version=3,
        )
        LOGGER.info("Migrated ArtNet DMX entry %s to version 3", entry.entry_id)
        return True

    if entry.version == 2 and len(fixture_records) > 1:
        LOGGER.error(
            "Entry %s uses an unsupported legacy multi-fixture format; remove and re-add fixtures individually",
            entry.entry_id,
        )
        return False

    LOGGER.error("Unsupported ArtNet DMX entry version %s", entry.version)
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up ArtNet DMX Controller from a config entry."""
    fixture_entry = get_fixture_entry(entry)
    target_ip = fixture_entry[CONF_TARGET_IP]
    universe = fixture_entry[CONF_UNIVERSE]

    artnet_helper, helper_key = await _async_acquire_helper(hass, target_ip, universe)

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = artnet_helper
    domain_data.setdefault(DATA_ENTRY_DATA, {})[entry.entry_id] = fixture_entry
    domain_data.setdefault(DATA_ENTRY_HELPER_KEYS, {})[entry.entry_id] = helper_key

    # Create/update a device registry entry so the integration appears under Devices
    # even if entities are disabled or not yet added.
    try:
        device_name = (
            fixture_entry.get(CONF_NAME)
            or getattr(entry, "title", None)
            or fixture_label(fixture_entry)
            or fixture_title(fixture_entry)
        )
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Art-Net",
            model=fixture_entry.get(CONF_FIXTURE_TYPE) or "DMX Fixture",
            name=device_name,
        )
    except Exception:  # pragma: no cover - best effort for non-HA/unit-test stubs
        LOGGER.debug("Could not register device for entry %s", entry.entry_id, exc_info=True)

    LOGGER.info(
        "ArtNet DMX fixture configured for %s (Universe %s)",
        target_ip,
        universe,
    )

    # Forward the setup to the light platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Unload the platforms
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await _async_release_helper(hass, entry.entry_id)
    return unloaded


async def _async_acquire_helper(
    hass: HomeAssistant,
    target_ip: str,
    universe: int,
) -> tuple[ArtNetDMXHelper, tuple[str, int]]:
    """Get or create a shared helper for one Art-Net target and universe."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    shared_helpers = domain_data.setdefault(DATA_SHARED_HELPERS, {})
    helper_refcounts = domain_data.setdefault(DATA_HELPER_REFCOUNTS, {})
    helper_lock = domain_data.setdefault(DATA_HELPER_LOCK, asyncio.Lock())
    helper_key = (target_ip, int(universe))

    async with helper_lock:
        artnet_helper = shared_helpers.get(helper_key)
        if artnet_helper is None:
            artnet_helper = ArtNetDMXHelper(hass=hass, target_ip=target_ip, universe=universe)
            artnet_helper.setup_socket()
            await artnet_helper.async_send_current_state()
            shared_helpers[helper_key] = artnet_helper
            helper_refcounts[helper_key] = 0
        helper_refcounts[helper_key] += 1

    return artnet_helper, helper_key


async def _async_release_helper(hass: HomeAssistant, entry_id: str) -> None:
    """Release a shared helper reference for one fixture entry."""
    domain_data = hass.data.get(DOMAIN, {})
    helper_key = domain_data.get(DATA_ENTRY_HELPER_KEYS, {}).pop(entry_id, None)
    domain_data.get(DATA_ENTRY_DATA, {}).pop(entry_id, None)
    domain_data.pop(entry_id, None)
    if helper_key is None:
        return

    shared_helpers = domain_data.get(DATA_SHARED_HELPERS, {})
    helper_refcounts = domain_data.get(DATA_HELPER_REFCOUNTS, {})
    helper_lock = domain_data.get(DATA_HELPER_LOCK)
    if helper_lock is None:
        return

    async with helper_lock:
        if helper_key not in helper_refcounts:
            return
        helper_refcounts[helper_key] -= 1
        if helper_refcounts[helper_key] <= 0:
            artnet_helper = shared_helpers.pop(helper_key, None)
            helper_refcounts.pop(helper_key, None)
            if artnet_helper is not None:
                artnet_helper.close_socket()
