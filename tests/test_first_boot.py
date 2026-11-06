import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('first_boot', SCRIPTS / 'first_boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class FirstBootTests(unittest.TestCase):
    def test_wifi_escapes_ssid_and_derives_psk(self):
        name, config = boot.settings(json.dumps({'hostname': 'my-board', 'wifi': {
            'ssid': 'a"\\\n网', 'password': 'test-only-password', 'country': 'CN'}}))
        self.assertEqual(name, 'my-board')
        self.assertIn('ssid=' + 'a"\\\n网'.encode().hex(), config)
        self.assertNotIn('test-only-password', config)
        self.assertRegex(config, r'psk=[0-9a-f]{64}\n')

    def test_rejects_bad_configuration(self):
        invalid = [{'hostname': '../root'}, {'hostname': 'a\nb'}, {'command': 'anything'},
                   {'wifi': {'ssid': 'x', 'password': 'short', 'country': 'CN'}},
                   {'wifi': {'ssid': 'x' * 33, 'password': 'test-only-password', 'country': 'CN'}},
                   {'wifi': {'ssid': 'x', 'password': 'test-only-password', 'country': 'CN\n'}}]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    boot.settings(json.dumps(value))
        for key in ['-----BEGIN OPENSSH PRIVATE KEY-----', 'command="echo hi" ssh-ed25519 AAAA', 'ssh-ed25519 AAAA']:
            with self.assertRaises(ValueError):
                boot.public_keys(key)

    @unittest.skipUnless(os.geteuid() == 0 and shutil.which('ssh-keygen'), 'provisioning integration requires root and OpenSSH')
    def test_import_is_validated_before_writes_and_consumed(self):
        with tempfile.TemporaryDirectory() as temp:
            root, config = Path(temp) / 'root', Path(temp) / 'setup'
            root.mkdir()
            config.mkdir()
            key = Path(temp) / 'key'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
            (config / 'authorized_keys').write_text(key.with_suffix('.pub').read_text())
            (config / 'setup.json').write_text('{"hostname": "../bad"}')
            with self.assertRaises(ValueError):
                boot.provision(root, config)
            self.assertFalse((root / 'home').exists())
            self.assertTrue((config / 'authorized_keys').exists())
            (config / 'setup.json').write_text(json.dumps({'hostname': 'test-board', 'wifi': {
                'ssid': 'test-network', 'password': 'test-only-password', 'country': 'CN'}}))
            self.assertEqual(boot.provision(root, config), 'test-board')
            self.assertFalse((config / 'setup.json').exists())
            self.assertFalse((config / 'authorized_keys').exists())
            self.assertTrue((root / 'var/lib/emb3533/initialized').exists())
            authorized = root / 'home/debian/.ssh/authorized_keys'
            self.assertEqual(authorized.stat().st_mode & 0o777, 0o600)
            self.assertEqual(authorized.stat().st_uid, 1000)
            wifi = root / 'etc/wpa_supplicant/wpa_supplicant-wlan0.conf'
            self.assertEqual(wifi.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('test-only-password', wifi.read_text())

    def test_missing_key_leaves_setup_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            root, config = Path(temp) / 'root', Path(temp) / 'config'
            root.mkdir()
            config.mkdir()
            with self.assertRaisesRegex(ValueError, 'SSH public key'):
                boot.provision(root, config)
            self.assertFalse((root / 'var/lib/emb3533/initialized').exists())


if __name__ == '__main__':
    unittest.main()
