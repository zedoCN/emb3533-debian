#!/usr/bin/python3
"""Create identities once, before networking; no preset Wi-Fi credentials."""
import hashlib
import os
from pathlib import Path
import subprocess


def main():
    if os.geteuid() != 0:
        raise SystemExit("root required")
    marker = Path('/var/lib/emb3533/initialized')
    if marker.exists():
        return
    machine_id = Path('/etc/machine-id').read_text().strip()
    if len(machine_id) != 32 or any(c not in '0123456789abcdef' for c in machine_id):
        raise SystemExit('systemd must generate a unique machine-id first')
    # Local unicast MAC, stable across boots and different for each machine-id.
    mac = bytearray(hashlib.sha256(('emb3533-eth0:' + machine_id).encode()).digest()[:6])
    mac[0] = (mac[0] & 0xfc) | 0x02
    address = ':'.join(f'{b:02x}' for b in mac)
    network = Path('/etc/network/interfaces.d/eth0')
    content = (
        'auto eth0\nallow-hotplug eth0\niface eth0 inet dhcp\n'
        f'    hwaddress ether {address}\n'
        '    pre-up /sbin/sysctl -q -w net.ipv4.conf.eth0.ignore_routes_with_linkdown=1\n'
    )
    if network.exists() and network.read_text() != content:
        raise SystemExit('refusing to overwrite an existing eth0 deployment config')
    temporary = network.with_name('.eth0.firstboot')
    temporary.write_text(content)
    temporary.chmod(0o644)
    temporary.replace(network)
    subprocess.run(['/usr/bin/ssh-keygen', '-A'], check=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('identities initialized\n')
    os.sync()


if __name__ == '__main__':
    main()
