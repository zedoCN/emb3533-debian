#!/usr/bin/env python3
"""Build a TF artifact from a user-owned boot prefix and a fresh rootfs.

Linux/root required for preserving rootfs ownership. Never flashes a device.
The base image has no deployment credentials. Vendor firmware is still supplied
privately by the board owner; review its distribution rights before publishing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
from first_boot import public_keys

PREFIX_BYTES = 124 * 1024**2
KERNEL_OFFSET = 36 * 1024**2
ROOT_LBA = 5177344
IMAGE_BYTES = 7 * 1024**3
CONFIG_LBA = 262144
CONFIG_SECTORS = 65536


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as src:
        for block in iter(lambda: src.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_root(root):
    if (root / 'etc/machine-id').read_bytes():
        raise ValueError('rootfs must have an empty machine-id')
    if list((root / 'etc/ssh').glob('ssh_host_*')):
        raise ValueError('rootfs must not contain SSH host keys')
    if list((root / 'etc/wpa_supplicant').glob('*.conf')):
        raise ValueError('rootfs must not contain Wi-Fi deployment credentials')
    if (root / 'var/lib/emb3533/initialized').exists():
        raise ValueError('rootfs has already been initialized')
    if (root / 'etc/network/interfaces.d/eth0').exists():
        raise ValueError('rootfs contains a deployed Ethernet identity')
    if (root / 'var/lib/emb3533/root-expanded').exists():
        raise ValueError('rootfs contains expansion state')
    if list((root / 'root/.ssh').glob('*')):
        raise ValueError('rootfs contains root SSH deployment files')
    if list((root / 'home').glob('*/.ssh/id_*')):
        raise ValueError('rootfs contains user SSH identity files')
    for entry in (root / 'etc/shadow').read_text().splitlines():
        if entry.split(':')[1][:1] not in ('!', '*'):
            raise ValueError('rootfs contains an unlocked password')
    if not (root / 'lib/systemd/systemd').is_file():
        raise ValueError('systemd is missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-prefix', required=True, type=Path, help='124MiB raw prefix from your own original backup')
    parser.add_argument('--rootfs', required=True, type=Path)
    parser.add_argument('--zimage', required=True, type=Path)
    parser.add_argument('--dtb', required=True, type=Path, help='TF variant with eMMC disabled')
    parser.add_argument('--authorized-keys', type=Path, help='optional deployment public keys for the FAT setup partition')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    root = args.rootfs.resolve()
    manifest = output.with_suffix(output.suffix + '.json')
    if os.geteuid() != 0:
        parser.error('run as root on Linux')
    if output == Path('/dev') or Path('/dev') in output.parents:
        parser.error('output must be a regular artifact')
    if output.exists() or manifest.exists():
        parser.error('output or manifest already exists')
    if root in output.parents:
        parser.error('output must be outside the rootfs input directory')
    if args.boot_prefix.stat().st_size != PREFIX_BYTES:
        parser.error('boot prefix must be exactly 124MiB; never use a live device')
    for src in (args.boot_prefix, args.zimage, args.dtb):
        if not src.is_file():
            parser.error('all artifact inputs must be regular files')
    validate_root(root)
    # Reject an eMMC or accidentally inherited enabled controller.
    status = subprocess.check_output(['fdtget', '-t', 's', str(args.dtb), '/mmc@ff0f0000', 'status'], text=True).strip()
    if status != 'disabled':
        parser.error('TF image requires eMMC disabled in the supplied DTB')
    signature = int.from_bytes(os.urandom(4), 'little') or 1
    partuuid = f'{signature:08x}-02'
    root_uuid = str(uuid.uuid4())
    root_start = ROOT_LBA * 512
    root_sectors = (IMAGE_BYTES - root_start) // 512
    with tempfile.TemporaryDirectory(prefix='emb3533-image-', dir=output.parent) as temp:
        temp = Path(temp)
        staging = temp / 'rootfs'
        subprocess.run(['cp', '-a', '--reflink=auto', str(root), str(staging)], check=True)
        legacy_key = staging / 'home/debian/.ssh/authorized_keys'
        key_source = args.authorized_keys or (legacy_key if legacy_key.exists() else None)
        keys = public_keys(key_source.read_text()) if key_source else None
        legacy_key.unlink(missing_ok=True)
        identity = {
            'format': 'emb3533-tf-v2', 'disk_signature': f'{signature:08x}',
            'root_uuid': root_uuid, 'root_sectors': root_sectors,
        }
        (staging / 'etc/emb3533-image.json').write_text(json.dumps(identity, indent=2) + '\n')
        packages = staging / 'usr/share/emb3533/packages.tsv'
        packages.parent.mkdir(parents=True, exist_ok=True)
        listing = subprocess.check_output([
            'dpkg-query', '--admindir=' + str(staging / 'var/lib/dpkg'),
            '-W', '-f=${binary:Package}\t${Version}\t${Architecture}\n',
        ], text=True)
        packages.write_text(listing)
        (staging / 'etc/fstab').write_text(f'UUID={root_uuid} / ext4 defaults,noatime 0 1\ntmpfs /tmp tmpfs defaults,nosuid,nodev,mode=1777 0 0\n')
        (staging / 'etc/emb3533-storage').write_text('tf\n')
        kernel = temp / 'kernel.img'
        subprocess.run([sys.executable, str(Path(__file__).with_name('make_kernel_image.py')), str(args.zimage), str(args.dtb), str(kernel), '--root', 'PARTUUID=' + partuuid], check=True)
        boot = staging / 'boot/emb3533'
        boot.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kernel, boot / 'tf-kernel.img')
        root_image = temp / 'root.ext4'
        root_image.touch()
        subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-F', '-b', '4096', '-L', 'DEBIANTF', '-U', root_uuid, '-d', str(staging), str(root_image), str(root_sectors // 8)], check=True)
        subprocess.run(['e2fsck', '-fn', str(root_image)], check=True)
        config_image = temp / 'setup.fat'
        with config_image.open('xb') as dest:
            dest.truncate(CONFIG_SECTORS * 512)
        subprocess.run(['mkfs.vfat', '-F', '16', '-n', 'EMBSETUP', str(config_image)], check=True)
        config_files = Path(__file__).parents[1] / 'config/first-boot'
        for name in ('README.txt', 'setup.json.example'):
            # Copy only the public templates, never editor/OS sidecar files.
            source = config_files / name
            subprocess.run(['mcopy', '-i', str(config_image), str(source), '::/'], check=True)
        if keys:
            key_file = temp / 'authorized_keys'
            key_file.write_text(keys)
            key_file.chmod(0o600)
            subprocess.run(['mcopy', '-i', str(config_image), str(key_file), '::/authorized_keys'], check=True)
        prefix = bytearray(args.boot_prefix.read_bytes())
        struct.pack_into('<I', prefix, 440, signature)
        prefix[446:510] = bytes(64)
        # FAT setup first for desktop readers; root retains its vendor-safe start.
        prefix[446:462] = struct.pack('<B3sB3sII', 0, b'\xfe\xff\xff', 0x0e, b'\xfe\xff\xff', CONFIG_LBA, CONFIG_SECTORS)
        prefix[462:478] = struct.pack('<B3sB3sII', 0, b'\xfe\xff\xff', 0x83, b'\xfe\xff\xff', ROOT_LBA, root_sectors)
        prefix[510:512] = b'\x55\xaa'
        image_kernel = kernel.read_bytes()
        prefix[KERNEL_OFFSET:KERNEL_OFFSET + len(image_kernel)] = image_kernel
        with output.open('xb') as dest:
            os.fchmod(dest.fileno(), 0o600)
            dest.truncate(IMAGE_BYTES)
            dest.write(prefix)
            dest.seek(CONFIG_LBA * 512)
            dest.write(config_image.read_bytes())
            with root_image.open('rb') as src:
                position = 0
                while block := src.read(1024**2):
                    if block.strip(b'\0'):
                        dest.seek(root_start + position)
                        dest.write(block)
                    position += len(block)
            dest.flush()
            os.fsync(dest.fileno())
        record = {
            **identity, 'bytes': IMAGE_BYTES, 'sha256': sha256(output),
            'root_start_lba': ROOT_LBA, 'root_sectors': root_sectors,
            'root_uuid': root_uuid, 'partuuid': partuuid,
            'boot_prefix_sha256': sha256(args.boot_prefix),
            'kernel_sha256': sha256(kernel), 'kernel_bytes': len(image_kernel),
            'zimage_sha256': sha256(args.zimage), 'dtb_sha256': sha256(args.dtb),
            'debian_version': (staging / 'etc/debian_version').read_text().strip(),
            'package_manifest_sha256': sha256(packages),
            'config_start_lba': CONFIG_LBA, 'config_sectors': CONFIG_SECTORS,
            'operator_key_supplied': bool(keys), 'root_expansion': 'first boot, SD only',
            'provisioning': 'EMBSETUP/authorized_keys and optional setup.json; unique host keys, machine-id and Ethernet MAC',
            'hardware_boot_verified': False,
        }
        with manifest.open('x') as dest:
            json.dump(record, dest, indent=2)
            dest.write('\n')
    print(f'Built {output}; first hardware boot remains to be verified')


if __name__ == '__main__':
    main()
