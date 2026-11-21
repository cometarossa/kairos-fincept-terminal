#!/usr/bin/env python3
"""Deterministic PNG fallback icon for offline Fincept Linux packaging.

No Pillow, font, display server, broker, network or third-party packages.
Keep the project's original icon when it exists; use this only as fallback.
"""

from pathlib import Path
import struct
import sys
import zlib

WIDTH = HEIGHT = 256
BACKGROUND = bytes((26, 26, 46, 255))
FOREGROUND = bytes((238, 151, 72, 255))
GLYPHS = {
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
}


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def generate_icon(path: Path) -> None:
    pixels = bytearray(BACKGROUND * (WIDTH * HEIGHT))
    scale, top, left = 18, 65, 32
    for col, char in enumerate(("F", "T")):
        for y, row in enumerate(GLYPHS[char]):
            for x, filled in enumerate(row):
                if filled != "1":
                    continue
                x0 = left + col * (5 * scale + 12) + x * scale
                y0 = top + y * scale
                for yy in range(y0, y0 + scale):
                    for xx in range(x0, x0 + scale):
                        at = (yy * WIDTH + xx) * 4
                        pixels[at : at + 4] = FOREGROUND

    stride = WIDTH * 4
    raw = b"".join(
        b"\x00" + pixels[y * stride : (y + 1) * stride]
        for y in range(HEIGHT)
    )
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 6, 0, 0, 0)
    png = (
        signature
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: create_fallback_icon.py OUTPUT.png")
    generate_icon(Path(sys.argv[1]))
