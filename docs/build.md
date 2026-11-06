# 构建内核与启动文件

## 构建范围

本流程生成内核、板级 DTB、匹配模块和 KRNL 内核文件。
它不准备分区表、Debian 根文件系统或原厂启动固件，也不会向块设备写入。
完整系统可继续使用 [镜像制作流程](images.md)，部署还需满足 [启动与恢复](boot-and-recovery.md) 中的条件。

在 Linux 构建机上安装依赖：

```sh
sudo apt install gcc-arm-linux-gnueabihf make bc bison flex \
  libssl-dev libelf-dev cpio curl python3 device-tree-compiler patch xz-utils
```

项目固定使用 Linux **7.3.1**，归档地址和 SHA-256 写在
[`scripts/build.sh`](../scripts/build.sh) 中。
这是经过适配的版本基线，不表示脚本会自动跟随 kernel.org 的最新版本。

## 编译

```sh
git clone https://github.com/zedoCN/emb3533-debian.git
cd emb3533-debian
bash scripts/build.sh
```

可用 `JOBS=4` 控制并行度，`WORK_DIR` 指定工作目录，`CROSS_COMPILE` 指定工具链前缀。
例如：

```sh
JOBS=4 WORK_DIR="$PWD/build" bash scripts/build.sh
```

脚本验证源码摘要，应用 timer 补丁，把 TF 与 eMMC 板级 DTS 放入 Rockchip DTS 目录，
从 `board/kernel.config` 还原配置，再构建内核与模块。
该配置是从实测配置导出的 savedefconfig；曾在独立输出目录还原并比对一致。
实机内核和模块已构建、安装及验证；当前公开脚本尚未在全新环境完成整套复现验证。

| 产物 | 默认位置 |
| --- | --- |
| zImage | `build/kernel-out/arch/arm/boot/zImage` |
| TF DTB | `build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dtb` |
| eMMC DTB | `build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-emmc.dtb` |
| 模块包 | `build/emb3533-7.3.1-modules.tar.gz` |

工作目录中的源码会被打补丁、复制 DTS；修改补丁或切换版本时建议使用新的 `WORK_DIR`。
已有源码目录会检查 timer 补丁是否已应用，脚本不会自动把旧工作树迁移成新版本。

## 生成 KRNL 内核文件

先确认目标机此次启动时的 TF 根分区。下面的 `/dev/mmcblk0p1` 仅代表本项目默认
DTS 下的实测布局；增加控制器后编号可能变化。

```sh
python3 scripts/make_kernel_image.py \
  build/kernel-out/arch/arm/boot/zImage \
  build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dtb \
  build/emb3533-kernel.img --root /dev/mmcblk0p1
```

eMMC 变体启用板载控制器，TF 控制器仍保留。它不会写盘，但根分区应使用稳定标识，
避免控制器探测顺序改变设备编号。工具支持 MBR/DOS 格式的 PARTUUID：

```sh
# 示例值，请替换为目标根分区实际的 PARTUUID。
emmc_partuuid=1a2b3c4d-01
python3 scripts/make_kernel_image.py \
  build/kernel-out/arch/arm/boot/zImage \
  build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-emmc.dtb \
  build/emb3533-emmc-kernel.img --root "PARTUUID=$emmc_partuuid"
```

PARTUUID 来自目标磁盘的分区表，不是 ext4 UUID。直接挂根不使用 initramfs，
此工具不接受依赖用户空间解析的 `UUID=` / `LABEL=` 根参数，也不自动探测目标磁盘。
eMMC 分区和系统迁移见 [迁移指南](emmc-migration.md)。

工具修改临时 DTB 的 `/chosen/bootargs`，设置根分区和 systemd 入口，移除 `rng-seed`，
将 DTB 追加到 zImage 后封装 KRNL。它保留输入文件，拒绝覆盖已有输出文件或输出到 `/dev/`。
输出不能超过已验证布局中 kernel 区的 24MiB。

[`pack_krnl.py`](../scripts/pack_krnl.py) 也可单独封装已经准备好的 payload；
它不会替你追加 DTB 或检查根文件系统条件。
KRNL 的 CRC 多项式为 `0x04c10db7`，不能换成常见的 zlib CRC32。
封装实现曾与厂商 `scripts/mkkrnlimg.c` 的已知产物做逐字节比对。

## 配置与部署配套

- 直接挂根要求 MMC、供电、I/O domain、ext4 等关键驱动内置；只编成模块会在挂根前不可用。
- 保持 `CONFIG_ARM_APPENDED_DTB=y`、`CONFIG_ARM_ATAG_DTB_COMPAT=n`。
- 内核启用 `CONFIG_CMDLINE_EXTEND`；不要在编译参数中固定 `init=/init`，覆盖 DT 中的 systemd 入口。
- 根文件系统使用 Debian **armhf**，配置 systemd、有线网络、OpenSSH、自己的 SSH 密钥，安装并启用 `jitterentropy-rngd`。
- 当前内核 release 为 `7.3.1-emb3533-power`。用 `scripts/install_modules.py` 将模块安装到目标根的 `usr/lib/modules/<kernelrelease>/`，再对该版本运行 `depmod`。
  不把其他版本模块复制过来凑数，也不要把含顶层 `lib/` 的归档直接解压到 `/`。
- 设置自己的稳定 MAC 或网络策略；公开 DTS 不包含实测设备的工厂 MAC。
- 板载 Wi-Fi 使用 `CONFIG_RTL8XXXU=m`，根系统还需固件与网络工具，见 [Wi-Fi 指南](wifi.md)。

如何更换目标存储的启动区、保留恢复点和确认启动成功，见 [启动与恢复](boot-and-recovery.md)。

## 工具测试

Linux 环境安装上述 device-tree-compiler 与 Python 后运行：

```sh
python3 -m unittest discover -s tests -v
```

测试覆盖 PARTUUID/设备路径封装、DT 种子移除、输入保留、错误参数拒绝与已有输出保护；
不操作磁盘、不替代内核编译或硬件启动验证。
