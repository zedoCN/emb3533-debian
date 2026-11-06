#!/usr/bin/env bash
# Build a new, personalized rootfs; never copies a running device or writes disks.
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# != 3 ]]; then
  echo "Usage: sudo $0 OUTPUT_DIRECTORY MODULES_TAR SSH_PUBLIC_KEY" >&2
  exit 2
fi
[[ $EUID == 0 ]] || { echo 'Run as root on a Linux build host.' >&2; exit 2; }
DEST=$(realpath -m -- "$1")
MODULES=$(realpath -- "$2")
PUBLIC_KEY=$(realpath -- "$3")
[[ ! -e "$DEST" && "$DEST" != / && "$DEST" != /dev/* ]] || exit 2
[[ -f "$MODULES" && -f "$PUBLIC_KEY" ]] || exit 2
ssh-keygen -l -f "$PUBLIC_KEY" >/dev/null
# Refuse accidentally supplied private keys or multiple provisioning lines.
[[ $(wc -l < "$PUBLIC_KEY") -le 1 ]] || exit 2
grep -Eq '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-[^ ]+) [A-Za-z0-9+/=]+([[:space:]].*)?$' "$PUBLIC_KEY" || exit 2
for program in debootstrap qemu-arm-static chroot tar; do command -v "$program" >/dev/null; done
mkdir -p -- "$DEST"
chmod 755 "$DEST"
debootstrap --arch=armhf --foreign --variant=minbase \
  --include=ca-certificates,systemd-sysv,dbus,udev,openssh-server,ifupdown,isc-dhcp-client,iproute2,iputils-ping,netbase,tzdata,sudo,curl,python3,kmod,busybox-static,jitterentropy-rngd,systemd-timesyncd,iw,wpasupplicant,usbutils \
  trixie "$DEST" "${DEBIAN_MIRROR:-https://deb.debian.org/debian}"
install -m755 "$(command -v qemu-arm-static)" "$DEST/usr/bin/qemu-arm-static"
printf '#!/bin/sh\nexit 101\n' > "$DEST/usr/sbin/policy-rc.d"
chmod 755 "$DEST/usr/sbin/policy-rc.d"
chroot "$DEST" /debootstrap/debootstrap --second-stage
cat > "$DEST/etc/apt/sources.list" <<EOF
deb ${DEBIAN_MIRROR:-https://deb.debian.org/debian} trixie main non-free-firmware
deb ${DEBIAN_MIRROR:-https://deb.debian.org/debian} trixie-updates main non-free-firmware
deb https://security.debian.org/debian-security trixie-security main non-free-firmware
EOF
chroot "$DEST" apt-get update
chroot "$DEST" env DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y --no-install-recommends
chroot "$DEST" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends firmware-realtek wireless-regdb
# This upstream kernel trusts the upstream regdb signing keys, not Debian's key.
chroot "$DEST" update-alternatives --set regulatory.db /lib/firmware/regulatory.db-upstream
python3 "$ROOT_DIR/scripts/install_modules.py" "$MODULES" "$DEST"
mapfile -t RELEASES < <(find "$DEST/lib/modules" -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
[[ ${#RELEASES[@]} == 1 ]] || { echo 'Expected exactly one module release.' >&2; exit 2; }
chroot "$DEST" depmod -a "${RELEASES[0]}"
chroot "$DEST" useradd --create-home --shell /bin/bash debian
install -d -m700 -o1000 -g1000 "$DEST/home/debian/.ssh"
install -m600 -o1000 -g1000 "$PUBLIC_KEY" "$DEST/home/debian/.ssh/authorized_keys"
printf 'debian ALL=(ALL) NOPASSWD:ALL\n' > "$DEST/etc/sudoers.d/debian"
chmod 440 "$DEST/etc/sudoers.d/debian"
printf 'emb3533-debian\n' > "$DEST/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 emb3533-debian\n::1 localhost ip6-localhost ip6-loopback\n' > "$DEST/etc/hosts"
printf 'auto lo\niface lo inet loopback\nsource /etc/network/interfaces.d/*\n' > "$DEST/etc/network/interfaces"
install -d "$DEST/etc/ssh/sshd_config.d"
printf 'PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n' > "$DEST/etc/ssh/sshd_config.d/emb3533.conf"
install -m755 "$ROOT_DIR/scripts/first_boot.py" "$DEST/usr/local/sbin/emb3533-first-boot"
install -m644 "$ROOT_DIR/config/emb3533-first-boot.service" "$DEST/etc/systemd/system/"
chroot "$DEST" systemctl enable emb3533-first-boot.service ssh.service jitterentropy.service systemd-timesyncd.service
chroot "$DEST" apt-get clean
rm -f "$DEST/usr/sbin/policy-rc.d" "$DEST/usr/bin/qemu-arm-static" "$DEST/etc/ssh/ssh_host_"* "$DEST/var/lib/dbus/machine-id" "$DEST/var/lib/systemd/random-seed"
ln -s /etc/machine-id "$DEST/var/lib/dbus/machine-id"
: > "$DEST/etc/machine-id"
find "$DEST/var/log" -type f -exec truncate -s0 {} +
printf 'Rootfs prepared: %s (account debian; SSH key authentication only)\n' "$DEST"
