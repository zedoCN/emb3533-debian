import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('grow_root', Path(__file__).parents[1] / 'scripts/grow_root.py')
grow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grow)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {'format': 'emb3533-tf-v2', 'disk_signature': '1234abcd', 'root_sectors': 9502720}
        self.mbr = bytearray(512)
        struct.pack_into('<I', self.mbr, 440, 0x1234abcd)
        self.mbr[446:462] = struct.pack('<B3sB3sII', 0, bytes(3), 0x0e, bytes(3), 262144, 65536)
        self.mbr[462:478] = struct.pack('<B3sB3sII', 0, bytes(3), 0x83, bytes(3), 5177344, 9502720)
        self.mbr[510:512] = b'\x55\xaa'

    def test_accepts_initial_and_expanded_layout(self):
        grow.check_layout(self.mbr, self.metadata)
        struct.pack_into('<I', self.mbr, 474, 490000000)
        grow.check_layout(self.mbr, self.metadata)

    def test_rejects_wrong_disk_start_setup_and_extra_partition(self):
        for offset in (440, 450, 454, 458, 466, 470, 482, 510):
            with self.subTest(offset=offset):
                changed = self.mbr.copy()
                changed[offset] ^= 1
                with self.assertRaises(ValueError):
                    grow.check_layout(changed, self.metadata)
        struct.pack_into('<I', self.mbr, 474, self.metadata['root_sectors'] - 1)
        with self.assertRaises(ValueError):
            grow.check_layout(self.mbr, self.metadata)


if __name__ == '__main__':
    unittest.main()
