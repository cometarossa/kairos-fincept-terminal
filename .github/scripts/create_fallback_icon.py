#!/usr/bin/env python3
"""Deterministic, no-Pillow PNG fallback for Linux Qt AppImage packaging."""
from pathlib import Path
import struct
import sys
import zlib

W = H = 256
BG = bytes((26, 26, 46, 255))
FG = bytes((238, 151, 72, 255))
GLYPHS = {
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
}

def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

def generate(path: Path) -> None:
    pixels = bytearray(BG * (W * H))
    scale, top, left = 18, 65, 32
    for col, ch in enumerate(("F", "T")):
        for y, row in enumerate(GLYPHS[ch]):
            for x, cell in enumerate(row):
                if cell != "1":
                    continue
                x0, y0 = left + col * (5 * scale + 12) + x * scale, top + y * scale
                for yy in range(y0, y0 + scale):
                    for xx in range(x0, x0 + scale):
                        pos = (yy * W + xx) * 4
                        pixels[pos : pos + 4] = FG
    stride = W * 4
    raw = b"".join(b"\x00" + pixels[y * stride : (y + 1) * stride] for y in range(H))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: create_fallback_icon.py OUTPUT.png")
    generate(Path(sys.argv[1]))
