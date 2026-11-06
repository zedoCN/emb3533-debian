import io
import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('install_modules', Path(__file__).parents[1] / 'scripts/install_modules.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModuleInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'root'
        (self.root / 'usr/lib').mkdir(parents=True)
        (self.root / 'lib').symlink_to('usr/lib')
        (self.root / 'usr/lib/loader-sentinel').write_text('preserved')

    def archive(self, name, symlink=False):
        path = self.base / 'modules.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            member = tarfile.TarInfo(name)
            if symlink:
                member.type = tarfile.SYMTYPE
                member.linkname = '/etc'
                archive.addfile(member)
            else:
                member.size = 6
                archive.addfile(member, io.BytesIO(b'module'))
        return path

    def test_preserves_merged_usr_and_refuses_overwrite(self):
        archive = self.archive('lib/modules/7.3.1-test/kernel/example.ko')
        self.assertEqual(module.install(archive, self.root), '7.3.1-test')
        self.assertTrue((self.root / 'lib').is_symlink())
        self.assertEqual((self.root / 'usr/lib/loader-sentinel').read_text(), 'preserved')
        self.assertEqual((self.root / 'usr/lib/modules/7.3.1-test/kernel/example.ko').read_bytes(), b'module')
        with self.assertRaises(FileExistsError):
            module.install(archive, self.root)

    def test_rejects_parent_entry_traversal_and_links(self):
        for name, symlink in [('lib/', False), ('lib/modules/x/../../etc/passwd', False), ('/lib/modules/x/a', False), ('lib/modules/x/link', True)]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    module.install(self.archive(name, symlink), self.root)
                self.assertTrue((self.root / 'lib').is_symlink())
                self.assertFalse((self.root / 'usr/lib/modules').exists())


if __name__ == '__main__':
    unittest.main()
