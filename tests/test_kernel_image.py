"""Exercise file-only boot image generation; never touches a block device."""
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'make_kernel_image.py'


@unittest.skipUnless(all(shutil.which(t) for t in ('dtc', 'fdtget', 'fdtput')),
                     'requires device-tree-compiler tools')
class KernelImageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='emb3533-test-')
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.zimage = self.base / 'zImage'
        self.zimage.write_bytes(b'test-kernel-payload')
        self.dtb = self.base / 'board.dtb'
        # A disposable fixture seed must remain in the input and leave the output.
        subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(self.dtb)],
                       input='/dts-v1/; / { chosen { rng-seed = [01 02 03 04]; }; };',
                       text=True, check=True, capture_output=True)
        self.output = self.base / 'kernel.img'

    def generate(self, root):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.zimage),
                               str(self.dtb), str(self.output), '--root', root],
                              text=True, capture_output=True)

    def assert_packaged_root(self, root):
        original = self.dtb.read_bytes()
        result = self.generate(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        image = self.output.read_bytes()
        self.assertEqual(image[:4], b'KRNL')
        self.assertEqual(len(image) % 512, 0)
        length = struct.unpack_from('<I', image, 4)[0]
        appended = self.base / 'appended.dtb'
        appended.write_bytes(image[8 + self.zimage.stat().st_size:8 + length])
        args = subprocess.check_output(['fdtget', '-t', 's', str(appended),
                                        '/chosen', 'bootargs'], text=True).split()
        self.assertIn('root=' + root, args)
        self.assertIn('init=/lib/systemd/systemd', args)
        props = subprocess.check_output(['fdtget', '-p', str(appended), '/chosen'], text=True)
        self.assertNotIn('rng-seed', props.splitlines())
        self.assertEqual(self.dtb.read_bytes(), original)

    def test_mbr_partuuid_root(self):
        self.assert_packaged_root('PARTUUID=1a2b3c4d-01')

    def test_existing_device_path_interface(self):
        self.assert_packaged_root('/dev/mmcblk0p1')

    def test_invalid_root_cannot_create_image(self):
        for root in ('PARTUUID=oops', 'PARTUUID=1a2b3c4d', 'UUID=example',
                     'LABEL=example', '/dev/mmcblk0p1 init=/init',
                     'PARTUUID=1a2b3c4d-01 init=/init'):
            with self.subTest(root=root):
                self.assertEqual(self.generate(root).returncode, 2)
                self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.write_bytes(b'keep-existing-artifact')
        self.assertNotEqual(self.generate('PARTUUID=1a2b3c4d-01').returncode, 0)
        self.assertEqual(self.output.read_bytes(), b'keep-existing-artifact')


if __name__ == '__main__':
    unittest.main()
