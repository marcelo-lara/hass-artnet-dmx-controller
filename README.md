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

## Python virtual environment

Create and activate a local Python virtual environment before running development commands.

### Linux / macOS

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
# from repo root
py -m venv .venv
.\.venv\Scripts\Activate.ps1
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
   - **Fixture Type**: The fixture model from `fixture_mapping.json`
   - **Base Channel**: The first DMX channel used by that fixture
   - **Fixture Name**: Optional Home Assistant display name for this fixture

## Usage

Each config entry represents one fixture. Fixtures that point to the same Art-Net target IP and universe still share one DMX universe buffer internally, so changing one fixture preserves the last values of the other channels in that universe while re-sending the full frame.

## Fixture Mapping & Config Flow

- This integration uses a shared `fixture_mapping.json` as the single source of truth for fixture models and channel definitions. Fixture models include channel offsets, channel counts, and optional `value_map` entries for selector-type channels.
- The initial config flow creates the fixture entry directly.
- Edit an existing fixture from the integration options by updating its target IP, universe, model, base channel, or display name.
- Channel overlap is validated across all fixtures that target the same IP and universe so entries cannot claim the same DMX addresses.

Note: Entities created for a fixture depend on the chosen `fixture_type` and `start_channel`. Names and numbers may therefore vary by model. DMX channels default to `0` on startup, and select entities derive an explicit initial option from that value when possible so Home Assistant does not render them as `unknown`.

Moving-head `pan` and `tilt` channels are exposed as numeric entities backed by their 16-bit DMX pairs. Updating one of these values writes the full 16-bit value and sends the corresponding MSB/LSB channel bytes to the shared universe buffer.

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
