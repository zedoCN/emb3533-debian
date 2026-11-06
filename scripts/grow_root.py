#!/usr/bin/python3
"""Expand only the recognized v2 image's TF root; never expand an eMMC root."""
import json
import os
from pathlib import Path
import struct
import subprocess


def check_layout(mbr, metadata):
    if metadata.get('format') != 'emb3533-tf-v2' or mbr[510:512] != b'\x55\xaa':
        raise ValueError('not a v2 TF image')
    if f'{struct.unpack_from("<I", mbr, 440)[0]:08x}' != metadata['disk_signature']:
        raise ValueError('disk signature does not match image metadata')
    config = struct.unpack_from('<B3sB3sII', mbr, 446)
    root = struct.unpack_from('<B3sB3sII', mbr, 462)
    if (config[0], config[2], config[4], config[5]) != (0, 0x0e, 262144, 65536):
        raise ValueError('unexpected configuration partition')
    if root[0] != 0 or root[2] != 0x83 or root[4] != 5177344 or root[5] < metadata['root_sectors']:
        raise ValueError('unexpected root partition')
    if any(mbr[478:510]):
        raise ValueError('unexpected extra partitions')


def expand(disk, root_device, metadata, state):
    with disk.open('rb') as source:
        before = source.read(512)
    check_layout(before, metadata)
    state.mkdir(parents=True, exist_ok=True)
    backup = state / 'mbr-before-expand.bin'
    if not backup.exists():
        with backup.open('xb') as dest:
            os.fchmod(dest.fileno(), 0o600)
            dest.write(before)
            dest.flush()
            os.fsync(dest.fileno())
    result = subprocess.run(['growpart', str(disk), '2'], capture_output=True, text=True)
    if result.returncode and not (result.returncode == 1 and result.stdout.startswith('NOCHANGE:')):
        raise RuntimeError('growpart failed; see the saved MBR and system journal')
    with disk.open('rb') as source:
        after = source.read(512)
    check_layout(after, metadata)
    # sfdisk normalizes legacy CHS fields in both entries. The LBA layout above
    # is authoritative; preserve boot code, disk signature and reserved bytes.
    if before[:446] != after[:446]:
        raise RuntimeError('unexpected change to MBR boot code or disk identity')
    subprocess.run(['resize2fs', str(root_device)], check=True)
    marker = state / 'root-expanded'
    marker.write_text('root partition and ext4 expanded\n')
    os.sync()


def main():
    if os.geteuid() != 0:
        raise SystemExit('root required')
    state = Path('/var/lib/emb3533')
    if (state / 'root-expanded').exists():
        return
    metadata = json.loads(Path('/etc/emb3533-image.json').read_text())
    major_minor = subprocess.check_output(['findmnt', '-n', '-o', 'MAJ:MIN', '/'], text=True).strip()
    sysroot = Path('/sys/dev/block', major_minor).resolve(strict=True)
    if (sysroot / 'partition').read_text().strip() != '2':
        raise ValueError('root is not the image partition 2')
    disk = sysroot.parent
    if (disk / 'device/type').read_text().strip() != 'SD':
        raise ValueError('automatic expansion is restricted to SD, never eMMC')
    root_device = Path('/dev', sysroot.name)
    actual_uuid = subprocess.check_output(['blkid', '-s', 'UUID', '-o', 'value', str(root_device)], text=True).strip()
    if actual_uuid != metadata['root_uuid']:
        raise ValueError('root filesystem UUID does not match image metadata')
    expand(Path('/dev', disk.name), root_device, metadata, state)


if __name__ == '__main__':
    main()
