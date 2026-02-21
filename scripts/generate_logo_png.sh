#!/usr/bin/env bash
set -euo pipefail

# Generate a PNG `logo.png` from the SVG `logo.svg` for the integration.
# Requires `rsvg-convert` (from librsvg) or `inkscape` on PATH.

SVG_PATH="custom_components/artnet_dmx_controller/logo.svg"
PNG_PATH="custom_components/artnet_dmx_controller/logo.png"
WIDTH=128
HEIGHT=128

if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -w "$WIDTH" -h "$HEIGHT" "$SVG_PATH" -o "$PNG_PATH"
  echo "Generated $PNG_PATH using rsvg-convert"
  exit 0
fi

if command -v inkscape >/dev/null 2>&1; then
  inkscape "$SVG_PATH" --export-type=png --export-filename="$PNG_PATH" --export-width="$WIDTH" --export-height="$HEIGHT"
  echo "Generated $PNG_PATH using inkscape"
  exit 0
fi

echo "Error: install 'rsvg-convert' (librsvg) or 'inkscape' to generate PNG from SVG" >&2
exit 2
