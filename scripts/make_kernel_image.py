#!/usr/bin/env python3
"""Append a board DTB and wrap zImage for the legacy Rockchip bootloader.

Requires CONFIG_ARM_APPENDED_DTB=y and CONFIG_ARM_ATAG_DTB_COMPAT=n.
Produces a file only. Does not flash a card or change its partition table.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from pack_krnl import pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zimage", type=Path)
    parser.add_argument("dtb", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", required=True, help="Root /dev/ path or DOS PARTUUID, such as PARTUUID=1a2b3c4d-01")
    args = parser.parse_args()
    if str(args.output.resolve()).startswith("/dev/"):
        parser.error("Output must be a regular artifact, not a device")
    root_is_device = args.root.startswith("/dev/")
    root_is_partuuid = re.fullmatch(r"PARTUUID=[0-9a-fA-F]{8}-[0-9a-fA-F]{2}", args.root) is not None
    if not (root_is_device or root_is_partuuid) or any(c.isspace() for c in args.root):
        parser.error("Root must be one /dev/ path or DOS PARTUUID=xxxxxxxx-xx")
    command_line = (
        f"root={args.root} rootfstype=ext4 rw rootwait init=/lib/systemd/systemd "
        "console=ttyS1,115200n8 earlycon=uart8250,mmio32,0xff190000 "
        "panic=10 oops=panic net.ifnames=0 clk_ignore_unused pd_ignore_unused "
        "systemd.mask=serial-getty@ttyFIQ0.service"
    )
    with tempfile.TemporaryDirectory(prefix="emb3533-kernel-") as directory:
        dtb = Path(directory) / "board.dtb"
        shutil.copyfile(args.dtb, dtb)
        subprocess.run(["fdtput", "-t", "s", str(dtb), "/chosen", "bootargs", command_line], check=True)
        # A persistent image must never embed a previously consumed RNG seed.
        properties = subprocess.check_output(["fdtget", "-p", str(dtb), "/chosen"], text=True).splitlines()
        if "rng-seed" in properties:
            subprocess.run(["fdtput", "-d", str(dtb), "/chosen", "rng-seed"], check=True)
        payload = args.zimage.read_bytes() + dtb.read_bytes()
    image = pack(payload)
    if len(image) > 24 * 1024**2:
        parser.error("Image exceeds the tested 24 MiB kernel area")
    with args.output.open("xb") as output:
        output.write(image)
    print(f"{len(image)} bytes sha256={hashlib.sha256(image).hexdigest()}")


if __name__ == "__main__":
    main()
