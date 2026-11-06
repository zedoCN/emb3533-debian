"""Linux integration: resize a disposable mounted loop image, never a host disk."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('grow_root', Path(__file__).parents[1] / 'scripts/grow_root.py')
grow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grow)
TOOLS = ('losetup', 'growpart', 'mke2fs', 'resize2fs', 'mount', 'umount', 'mkfs.vfat')


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and all(shutil.which(x) for x in TOOLS), 'requires Linux/root and filesystem tools')
class OnlineExpansionTests(unittest.TestCase):
    def test_online_growth_preserves_setup_boot_code_and_root_files(self):
        with tempfile.TemporaryDirectory(prefix='emb3533-growth-') as temp:
            base = Path(temp)
            image = base / 'disposable.img'
            initial_sectors = 7 * 1024**3 // 512 - 5177344
            metadata = {'format': 'emb3533-tf-v2', 'disk_signature': '1234abcd', 'root_sectors': initial_sectors}
            mbr = bytearray(512)
            mbr[:440] = b'B' * 440
            struct.pack_into('<I', mbr, 440, 0x1234abcd)
            for offset, kind, start, size in [(446, 0x0e, 262144, 65536), (462, 0x83, 5177344, initial_sectors)]:
                mbr[offset:offset + 16] = struct.pack('<B3sB3sII', 0, b'\xfe\xff\xff', kind, b'\xfe\xff\xff', start, size)
            mbr[510:512] = b'\x55\xaa'
            with image.open('wb') as dest:
                dest.truncate(8 * 1024**3)
                dest.write(mbr)
                dest.seek(36 * 1024**2)
                dest.write(b'kernel-sentinel')
            loop = subprocess.check_output(['losetup', '--find', '--show', '--partscan', str(image)], text=True).strip()
            mount = base / 'mount'
            mount.mkdir()
            mounted = False
            try:
                setup_device, root_device = Path(loop + 'p1'), Path(loop + 'p2')
                subprocess.run(['mkfs.vfat', '-F', '16', str(setup_device)], check=True, capture_output=True)
                setup_hash = hashlib.sha256(setup_device.read_bytes()).hexdigest()
                subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-F', str(root_device)], check=True)
                subprocess.run(['mount', str(root_device), str(mount)], check=True)
                mounted = True
                sentinel = mount / 'preserve-me'
                sentinel.write_text('root data survives online expansion\n')
                before = os.statvfs(mount).f_blocks
                state = mount / 'var/lib/emb3533'
                grow.expand(Path(loop), root_device, metadata, state)
                self.assertGreater(os.statvfs(mount).f_blocks, before)
                self.assertTrue((state / 'root-expanded').exists())
                self.assertEqual(sentinel.read_text(), 'root data survives online expansion\n')
                self.assertEqual(hashlib.sha256(setup_device.read_bytes()).hexdigest(), setup_hash)
                with image.open('rb') as source:
                    source.seek(36 * 1024**2)
                    self.assertEqual(source.read(15), b'kernel-sentinel')
                # NOCHANGE after a successful expansion is safe and repeatable.
                grow.expand(Path(loop), root_device, metadata, state)
            finally:
                if mounted:
                    subprocess.run(['umount', str(mount)], check=True)
                subprocess.run(['losetup', '-d', loop], check=True)


if __name__ == '__main__':
    unittest.main()
