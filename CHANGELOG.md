# Changelog

## Unreleased

 - Moved `dmx_scene` functionality into `custom_components/artnet_dmx_controller/scene/`.
 - Added config flow inputs for fixture creation (`fixture_type`, `start_channel`), validation and mapping-driven entity creation.
 - Implemented centralized DMX writer with batching and fallback.
 - Added scene record/play/list/delete services under `artnet_dmx_controller` domain.
 - Updated README and docs to reflect integration restructuring.
 - Updated `hacs.json` metadata for HACS compatibility.
