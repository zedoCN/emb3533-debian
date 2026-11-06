#!/usr/bin/python3
"""Initialize identities and consume declarative settings from the FAT partition."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def write_atomic(path, content, mode=0o644, owner=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.firstboot')
    with temporary.open('w') as dest:
        os.fchmod(dest.fileno(), mode)
        if owner:
            os.fchown(dest.fileno(), *owner)
        dest.write(content)
        dest.flush()
        os.fsync(dest.fileno())
    temporary.replace(path)


def read_small(path, limit=65536):
    with path.open('rb') as src:
        content = src.read(limit + 1)
    if len(content) > limit:
        raise ValueError('first-boot configuration is too large')
    return content.decode('utf-8')


def public_keys(content):
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) < 2 or not re.fullmatch(r'ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)', fields[0]):
            raise ValueError('authorized_keys must contain plain public keys without options')
        try:
            base64.b64decode(fields[1], validate=True)
        except ValueError:
            raise ValueError('invalid SSH public key') from None
        # Check the actual key structure, not only the textual prefix.
        with tempfile.NamedTemporaryFile(mode='w') as keyfile:
            keyfile.write(' '.join(fields[:2]) + '\n')
            keyfile.flush()
            result = subprocess.run(['ssh-keygen', '-l', '-f', keyfile.name], capture_output=True)
        if result.returncode:
            raise ValueError('invalid SSH public key')
        lines.append(' '.join(fields[:2]))  # comments need not become deployment identity
    if not lines:
        raise ValueError('at least one SSH public key is required')
    return '\n'.join(lines) + '\n'


def settings(content):
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError):
        raise ValueError('setup.json is not valid UTF-8 JSON') from None
    if not isinstance(value, dict) or set(value) - {'hostname', 'wifi'}:
        raise ValueError('unknown first-boot setting')
    hostname = value.get('hostname', 'emb3533-debian')
    if not isinstance(hostname, str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', hostname):
        raise ValueError('hostname must be one lowercase DNS label')
    wifi_config = None
    if 'wifi' in value:
        wifi = value['wifi']
        if not isinstance(wifi, dict) or set(wifi) != {'ssid', 'password', 'country'}:
            raise ValueError('wifi requires ssid, password and country')
        ssid, password, country = wifi['ssid'], wifi['password'], wifi['country']
        if not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32:
            raise ValueError('Wi-Fi SSID must be 1-32 UTF-8 bytes')
        if not isinstance(country, str) or not re.fullmatch('[A-Z]{2}', country):
            raise ValueError('country must be a two-letter uppercase code')
        if not isinstance(password, str):
            raise ValueError('invalid Wi-Fi password')
        if re.fullmatch('[0-9a-fA-F]{64}', password):
            psk = password.lower()
        elif 8 <= len(password.encode()) <= 63:
            psk = hashlib.pbkdf2_hmac('sha1', password.encode(), ssid.encode(), 4096, 32).hex()
        else:
            raise ValueError('Wi-Fi password must be 8-63 bytes or a 64-digit hex PSK')
        wifi_config = (f'ctrl_interface=DIR=/run/wpa_supplicant GROUP=netdev\ncountry={country}\n'
                       f'network={{\n    ssid={ssid.encode().hex()}\n    psk={psk}\n    scan_ssid=1\n}}\n')
    return hostname, wifi_config


def provision(root, config):
    """Validate all inputs before applying them; repeatable after interrupted import."""
    authorized = root / 'home/debian/.ssh/authorized_keys'
    supplied_keys = config / 'authorized_keys'
    if not supplied_keys.exists() and not authorized.exists():
        raise ValueError('copy your SSH public key to EMBSETUP/authorized_keys, then reboot')
    keys = public_keys(read_small(supplied_keys if supplied_keys.exists() else authorized))
    setup = config / 'setup.json'
    hostname, wifi = settings(read_small(setup)) if setup.exists() else ('emb3533-debian', None)
    authorized.parent.mkdir(parents=True, exist_ok=True)
    authorized.parent.chmod(0o700)
    os.chown(authorized.parent, 1000, 1000)
    write_atomic(authorized, keys, 0o600, (1000, 1000))
    write_atomic(root / 'etc/hostname', hostname + '\n')
    write_atomic(root / 'etc/hosts', f'127.0.0.1 localhost\n127.0.1.1 {hostname}\n::1 localhost ip6-localhost ip6-loopback\n')
    if wifi:
        write_atomic(root / 'etc/wpa_supplicant/wpa_supplicant-wlan0.conf', wifi, 0o600)
        write_atomic(root / 'etc/network/interfaces.d/wlan0',
                     'allow-hotplug wlan0\niface wlan0 inet dhcp\n'
                     '    wpa-conf /etc/wpa_supplicant/wpa_supplicant-wlan0.conf\n'
                     '    metric 600\n'
                     '    pre-up /sbin/sysctl -q -w net.ipv6.conf.wlan0.accept_ra=0\n')
    # Commit credentials to ext4 before removing the import files. FAT unlink does
    # not securely erase flash; the configuration card must remain private.
    os.sync()
    supplied_keys.unlink(missing_ok=True)
    setup.unlink(missing_ok=True)
    os.sync()
    write_atomic(root / 'var/lib/emb3533/initialized', 'identities and deployment settings initialized\n', 0o600)
    os.sync()
    return hostname


def main():
    if os.geteuid() != 0:
        raise SystemExit('root required')
    if Path('/var/lib/emb3533/initialized').exists():
        return
    machine_id = Path('/etc/machine-id').read_text().strip()
    if not re.fullmatch('[0-9a-f]{32}', machine_id):
        raise SystemExit('systemd must generate a unique machine-id first')
    mac = bytearray(hashlib.sha256(('emb3533-eth0:' + machine_id).encode()).digest()[:6])
    mac[0] = (mac[0] & 0xfc) | 0x02
    address = ':'.join(f'{b:02x}' for b in mac)
    network = Path('/etc/network/interfaces.d/eth0')
    content = ('auto eth0\nallow-hotplug eth0\niface eth0 inet dhcp\n'
               f'    hwaddress ether {address}\n'
               '    pre-up /sbin/sysctl -q -w net.ipv4.conf.eth0.ignore_routes_with_linkdown=1\n')
    if network.exists() and network.read_text() != content:
        raise SystemExit('refusing to overwrite an existing eth0 deployment config')
    write_atomic(network, content)
    subprocess.run(['ssh-keygen', '-A'], check=True)
    metadata = json.loads(Path('/etc/emb3533-image.json').read_text())
    signature = metadata['disk_signature']
    if not re.fullmatch('[0-9a-f]{8}', signature):
        raise ValueError('invalid setup partition identity')
    device = subprocess.check_output(['blkid', '-t', f'PARTUUID={signature}-01', '-o', 'device'], text=True).splitlines()
    if len(device) != 1:
        raise ValueError('cannot uniquely locate the setup partition')
    if subprocess.check_output(['blkid', '-s', 'TYPE', '-o', 'value', device[0]], text=True).strip() != 'vfat':
        raise ValueError('setup partition is not FAT')
    directory = Path('/run/emb3533-setup')
    directory.mkdir(mode=0o700, exist_ok=True)
    subprocess.run(['mount', '-t', 'vfat', '-o', 'rw,nodev,nosuid,noexec,umask=0077', device[0], str(directory)], check=True)
    try:
        hostname = provision(Path('/'), directory)
        Path('/proc/sys/kernel/hostname').write_text(hostname)
    finally:
        subprocess.run(['umount', str(directory)], check=True)


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from None
