#!/usr/bin/env python3
"""Render the traced logo into PNG files at multiple sizes without external deps.

Produces: custom_components/artnet_dmx_controller/logo_128.png,
          custom_components/artnet_dmx_controller/logo_64.png,
          custom_components/artnet_dmx_controller/logo_32.png
Also writes/overwrites logo.png with the 128 PNG.
"""
import os
import zlib
import struct


def make_png(path, width, height, rgb_buffer):
    # rgb_buffer: bytes length width*height*3
    raw_lines = []
    for y in range(height):
        start = y * width * 3
        line = b"\x00" + rgb_buffer[start:start + width * 3]
        raw_lines.append(line)
    raw = b"".join(raw_lines)
    comp = zlib.compress(raw, 9)

    png = b"\x89PNG\r\n\x1a\n"
    # IHDR
    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,
        2,  # RGB
        0,
        0,
        0,
    )
    png += struct.pack(
        ">I", len(ihdr)
    ) + b"IHDR" + ihdr
    png += struct.pack(
        ">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF
    )

    png += struct.pack(
        ">I", len(comp)
    ) + b"IDAT" + comp
    png += struct.pack(
        ">I", zlib.crc32(b"IDAT" + comp) & 0xFFFFFFFF
    )

    png += struct.pack(
        ">I", 0
    ) + b"IEND" + b""
    png += struct.pack(
        ">I", zlib.crc32(b"IEND") & 0xFFFFFFFF
    )

    with open(path, "wb") as f:
        f.write(png)


def filled_circle(buf, w, h, cx, cy, r, color):
    r2 = r * r
    for y in range(max(0, cy - r), min(h, cy + r + 1)):
        dy = y - cy
        dy2 = dy * dy
        # compute horizontal span
        dx = int((r2 - dy2) ** 0.5) if r2 >= dy2 else -1
        if dx >= 0:
            x0 = max(0, cx - dx)
            x1 = min(w - 1, cx + dx)
            for x in range(x0, x1 + 1):
                i = (y * w + x) * 3
                buf[i:i+3] = bytes(color)


def filled_rect(buf, w, h, x0, y0, rw, rh, color):
    x1 = max(0, x0)
    y1 = max(0, y0)
    x2 = min(w, x0 + rw)
    y2 = min(h, y0 + rh)
    for y in range(y1, y2):
        for x in range(x1, x2):
            i = (y * w + x) * 3
            buf[i:i+3] = bytes(color)


def rounded_rect_fill(buf, w, h, x, y, rw, rh, rad, color):
    # fill central rect
    filled_rect(buf, w, h, x + rad, y, rw - 2 * rad, rh, color)
    filled_rect(buf, w, h, x, y + rad, rw, rh - 2 * rad, color)
    # corners
    filled_circle(buf, w, h, x + rad, y + rad, rad, color)
    filled_circle(buf, w, h, x + rw - rad - 1, y + rad, rad, color)
    filled_circle(buf, w, h, x + rad, y + rh - rad - 1, rad, color)
    filled_circle(buf, w, h, x + rw - rad - 1, y + rh - rad - 1, rad, color)


def render(size):
    w = h = size
    buf = bytearray(b"\x00" * (w * h * 3))
    # background black already

    # outer rounded box stroke: draw outer white rounded rect then inner black rounded rect to make stroke
    stroke = 3 * size // 128  # scale stroke with size
    outer_x = int(8 * size / 128)
    outer_y = int(22 * size / 128)
    outer_w = int(112 * size / 128)
    outer_h = int(84 * size / 128)
    rad = max(1, int(6 * size / 128))
    rounded_rect_fill(buf, w, h, outer_x, outer_y, outer_w, outer_h, rad, (255,255,255))
    inner_x = outer_x + stroke
    inner_y = outer_y + stroke
    inner_w = outer_w - 2*stroke
    inner_h = outer_h - 2*stroke
    inner_rad = max(0, rad - stroke)
    rounded_rect_fill(buf, w, h, inner_x, inner_y, inner_w, inner_h, inner_rad, (0,0,0))

    # top knobs (white circles)
    knob_r = max(2, int(6 * size / 128))
    knobs = [ (28,34), (48,34), (68,34), (88,34) ]
    for (kx,ky) in knobs:
        filled_circle(buf, w, h, int(kx * size / 128), int(ky * size / 128), knob_r, (255,255,255))

    # DMX label blue rounded rect
    dm_x = int(12 * size / 128)
    dm_y = int(44 * size / 128)
    dm_w = int(22 * size / 128)
    dm_h = int(14 * size / 128)
    dm_rad = max(1, int(3 * size / 128))
    rounded_rect_fill(buf, w, h, dm_x, dm_y, dm_w, dm_h, dm_rad, (10,132,255))

    # sliders (white rectangles)
    def rect_scaled(x,y,ww,hh):
        return int(x*size/128), int(y*size/128), int(ww*size/128), int(hh*size/128)

    filled_rect(buf, w, h, *rect_scaled(44,54,4,30), (255,255,255))
    filled_rect(buf, w, h, *rect_scaled(56,50,4,34), (255,255,255))
    filled_rect(buf, w, h, *rect_scaled(68,58,4,26), (255,255,255))

    # joystick: small circle + vertical stick line (white)
    jcx = int(98 * size / 128)
    jcy = int(58 * size / 128)
    jr = max(3, int(8 * size / 128))
    filled_circle(buf, w, h, jcx, jcy, jr, (255,255,255))
    # stick: draw vertical line by small rect
    stick_x = jcx - max(0, int(1 * size / 128))
    stick_y = jcy + jr
    filled_rect(buf, w, h, stick_x, stick_y, max(2, int(2*size/128)), int(12*size/128), (255,255,255))

    # blue indicator LEDs four small blue circles
    leds = [ (94,86), (106,86), (94,98), (106,98) ]
    lr = max(2, int(4 * size / 128))
    for (lx,ly) in leds:
        filled_circle(buf, w, h, int(lx*size/128), int(ly*size/128), lr, (0,150,255))

    return bytes(buf)


def main():
    out_dir = "custom_components/artnet_dmx_controller"
    os.makedirs(out_dir, exist_ok=True)
    sizes = [128, 64, 32]
    for s in sizes:
        buf = render(s)
        out = os.path.join(out_dir, f"logo_{s}.png")
        make_png(out, s, s, buf)
        print("Wrote", out)
    # also copy 128 to logo.png
    logo128 = os.path.join(out_dir, "logo_128.png")
    main_logo = os.path.join(out_dir, "logo.png")
    with open(logo128, 'rb') as f_in, open(main_logo, 'wb') as f_out:
        f_out.write(f_in.read())
    print("Wrote", main_logo)


if __name__ == '__main__':
    main()
