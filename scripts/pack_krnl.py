#!/usr/bin/env python3
"""Build a Rockchip KRNL container; never writes to a device.

Format matches Rockchip kernel/scripts/mkkrnlimg.c (GPL-2.0-or-later).
The vendor polynomial is 0x04c10db7, not the usual zlib CRC32.
"""
import argparse
import hashlib
from pathlib import Path
import struct


def pack(payload: bytes) -> bytes:
    table = []
    for index in range(256):
        value = index << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C10DB7 if value & 0x80000000 else 0)) & 0xFFFFFFFF
        table.append(value)
    crc = 0
    for byte in payload:
        crc = ((crc << 8) ^ table[(crc >> 24) ^ byte]) & 0xFFFFFFFF
    image = b"KRNL" + struct.pack("<I", len(payload)) + payload + struct.pack("<I", crc)
    return image.ljust((len(image) + 511) // 512 * 512, b"\0")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if str(args.output.resolve()).startswith("/dev/"):
        parser.error("Output must be a regular artifact, not a device")
    image = pack(args.payload.read_bytes())
    if len(image) > 24 * 1024**2:
        parser.error("Image exceeds the tested 24 MiB kernel area")
    with args.output.open("xb") as output:
        output.write(image)
    print(f"{len(image)} bytes sha256={hashlib.sha256(image).hexdigest()}")


if __name__ == "__main__":
    main()
