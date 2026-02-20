# [DO NOT DOWNLOAD (YET)] ArtNet DMX Controller

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

A Home Assistant custom integration for controlling DMX devices via the Art-Net protocol.

## Features

- **Local Push Communication**: Uses UDP sockets for direct Art-Net communication
- **No External Dependencies**: Built using only Python's built-in socket and struct modules
- **Full Asyncio Support**: All operations are async-compatible
- **UI Configuration**: Easy setup through Home Assistant's UI
- **DMX Light Entities**: Control DMX channels as Home Assistant light entities with brightness control

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "ArtNet DMX Controller" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/artnet_dmx_controller` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Installation instructions

### HACS (recommended)
1. In Home Assistant, go to Settings → Integrations → HACS (Community Store).
2. Add this repository as a custom repository (type: Integration, category: Integration).
3. Search for "ArtNet DMX Controller" in HACS and click Install.
4. Restart Home Assistant.
5. Configure the integration via Settings → Devices & Services → Add Integration → "ArtNet DMX Controller".

### Manual installation
1. Copy the integration folder to your Home Assistant `custom_components` directory:

```bash
# from repo root
cp -r custom_components/artnet_dmx_controller /config/custom_components/
```
2. Restart Home Assistant.
3. Configure the integration via Settings → Devices & Services → Add Integration → "ArtNet DMX Controller".

### Quick verification
- After restart, the integration should appear in Settings → Devices & Services.
- Example entities created: `light.dmx_channel_1`, `light.dmx_channel_2`, etc.
- If you do not see the integration, check Home Assistant logs for `artnet_dmx_controller` errors.

### Notes
- This integration uses Art-Net (UDP) to send DMX; ensure your target device IP and network allow UDP/6454 traffic.
- For development/testing, run Home Assistant in a dev environment and monitor logs while adding the integration.

## Python virtual environment (`hass`)

Create and activate a local Python virtual environment named `hass` before running development commands.

### Linux / macOS

```bash
# from repo root
python3 -m venv hass
source hass/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
# from repo root
py -m venv hass
.\hass\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Deactivate

```bash
deactivate
```

### Running tests

Use the `hass` virtual environment bundled in this repository. You can either activate it, or run commands directly with the included interpreter. Example (recommended):

```bash
# from repo root — install or upgrade pip first
hass/bin/python -m pip install --upgrade pip
hass/bin/python -m pip install -r requirements.txt

# Run tests using the hass interpreter
hass/bin/python -m pytest -q
```

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "ArtNet DMX Controller"
4. Enter the configuration:
   - **Target IP Address**: The IP address of your Art-Net device
   - **Universe**: The Art-Net universe number (0-32767)

## Usage

After configuration, the integration will create 10 light entities (DMX channels 1-10) that you can control through Home Assistant:

- **Turn On/Off**: Control individual DMX channels
- **Brightness**: Set DMX values from 0-255

Example entity names:
- `light.dmx_channel_1`
- `light.dmx_channel_2`
- etc.

## Fixture Mapping & Config Flow

- This integration uses a shared `fixture_mapping.json` as the single source of truth for fixture models and channel definitions. Fixture models include channel offsets, channel counts, and optional `value_map` entries for selector-type channels.
- When adding a new fixture via the UI (no YAML required), the config flow will prompt for a `fixture_type` (model) and a `start_channel`. The integration will create a device and child entities derived from the selected model.

Note: Entities created for a fixture depend on the chosen `fixture_type` and `start_channel`. Names and numbers may therefore vary by model.

## Scenes (Record / Play)

The integration provides simple scene persistence and playback services registered under the integration domain (`artnet_dmx_controller`). These services operate on the DMX-level payloads captured from the current integration state.

Service names and example usage (Developer Tools → Services):

- `artnet_dmx_controller.record_scene` — Record the current DMX state for an entry (config entry) into a named scene.
   - Required data: `entry_id` (the config entry id), `name` (scene name)

Example (YAML payload in Developer Tools):

```yaml
service: artnet_dmx_controller.record_scene
data:
   entry_id: your_entry_id_here
   name: evening_preset
```

- `artnet_dmx_controller.play_scene` — Play an existing scene for a given entry.
   - Required data: `entry_id`, `name`; Optional: `transition` (seconds)

```yaml
service: artnet_dmx_controller.play_scene
data:
   entry_id: your_entry_id_here
   name: evening_preset
   transition: 1
```

- `artnet_dmx_controller.list_scenes` — Log or list available scenes (no data required).

- `artnet_dmx_controller.delete_scene` — Delete a saved scene by name.
   - Required data: `name`

```yaml
service: artnet_dmx_controller.delete_scene
data:
   name: evening_preset
```

Scenes are stored in the integration's internal storage and survive restarts.

## Art-Net Protocol Details

This integration implements the Art-Net protocol for DMX lighting control:

- **Protocol Version**: Art-Net 14
- **OpCode**: OpOutput (0x5000)
- **Port**: 6454 (standard Art-Net port)
- **Packet Structure**: Manually constructed using Python's struct module
- **DMX Channels**: 512 channels per universe

## Technical Details

### Components

- **manifest.json**: Integration metadata (version 1.0.0, iot_class: local_push)
- **const.py**: Shared constants (DOMAIN, DEFAULT_PORT: 6454)
- **artnet.py**: Art-Net packet construction and UDP communication helper
- **__init__.py**: Integration setup and UDP socket initialization
- **light.py**: DMX channel light platform
- **config_flow.py**: UI configuration flow

### Art-Net Packet Structure

The integration constructs Art-Net DMX packets with the following structure:

```
Header:    "Art-Net\x00" (8 bytes)
OpCode:    0x5000 (2 bytes, little-endian)
ProtVer:   14 (2 bytes, big-endian)
Sequence:  0 (1 byte)
Physical:  0 (1 byte)
SubUni:    subnet + universe (1 byte)
Net:       0 (1 byte)
Length:    512 (2 bytes, big-endian)
Data:      DMX data (512 bytes)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter any issues or have questions, please [open an issue](https://github.com/marcelo-lara/hass-artnet-dmx-controller/issues).

[releases-shield]: https://img.shields.io/github/release/marcelo-lara/hass-artnet-dmx-controller.svg?style=for-the-badge
[releases]: https://github.com/marcelo-lara/hass-artnet-dmx-controller/releases
[license-shield]: https://img.shields.io/github/license/marcelo-lara/hass-artnet-dmx-controller.svg?style=for-the-badge
