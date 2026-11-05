#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
WORK_DIR=${WORK_DIR:-"$ROOT_DIR/build"}
VERSION=7.3.1
SHA256=fa595aad93734f829c963c2a90ef7c3673224fd7fdae7b49406e397cde2de231
mkdir -p "$WORK_DIR"
WORK_DIR=$(cd -- "$WORK_DIR" && pwd)
ARCHIVE="$WORK_DIR/linux-$VERSION.tar.xz"
if [[ ! -f "$ARCHIVE" ]]; then
  curl --fail --location "https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-$VERSION.tar.xz" -o "$ARCHIVE"
fi
printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum -c -
SOURCE_DIR="$WORK_DIR/linux-$VERSION"
if [[ ! -d "$SOURCE_DIR" ]]; then
  tar -C "$WORK_DIR" -xf "$ARCHIVE"
  patch -d "$SOURCE_DIR" -p1 < "$ROOT_DIR/patches/0001-emb3533-preserve-firmware-timer.patch"
fi
patch --dry-run --reverse --batch -d "$SOURCE_DIR" -p1 < "$ROOT_DIR/patches/0001-emb3533-preserve-firmware-timer.patch" > /dev/null
cp "$ROOT_DIR/board/rk3288-emb3533.dts" "$SOURCE_DIR/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dts"
export ARCH=arm CROSS_COMPILE=${CROSS_COMPILE:-arm-linux-gnueabihf-}
OUTPUT_DIR="$WORK_DIR/kernel-out"
mkdir -p "$OUTPUT_DIR"
cp "$ROOT_DIR/board/kernel.config" "$OUTPUT_DIR/.config"
make -C "$SOURCE_DIR" O="$OUTPUT_DIR" olddefconfig
make -C "$SOURCE_DIR" O="$OUTPUT_DIR" -j"${JOBS:-4}" zImage rockchip/rk3288-emb3533-trial.dtb modules
MODULES_DIR="$WORK_DIR/modules"
make -C "$SOURCE_DIR" O="$OUTPUT_DIR" INSTALL_MOD_PATH="$MODULES_DIR" INSTALL_MOD_STRIP=1 modules_install
find "$MODULES_DIR/lib/modules" -maxdepth 2 -type l \( -name build -o -name source \) -delete
tar --owner=0 --group=0 -C "$MODULES_DIR" -czf "$WORK_DIR/emb3533-$VERSION-modules.tar.gz" "lib/modules/$VERSION-emb3533"
printf 'Built %s and %s\n' "$OUTPUT_DIR/arch/arm/boot/zImage" "$OUTPUT_DIR/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dtb"
