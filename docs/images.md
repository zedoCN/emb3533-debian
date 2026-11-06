# 制作 Debian 命令行 TF 镜像

本流程生成 **7GiB TF 整卡文件**，使用项目内核、干净的 Debian 13 armhf 根文件系统，
以及部署者自行提供的原厂启动前缀。工具只生成文件，不识别或写入读卡器。
TF 镜像不能直接当成 eMMC 安装包；eMMC 使用 [迁移流程](emmc-migration.md)。

## 准备输入

在能够通过 binfmt/QEMU 运行 armhf chroot 的 Linux 构建机上安装依赖：

```sh
sudo apt install debootstrap qemu-user-static binfmt-support \
  openssh-client e2fsprogs python3
```

同时准备 [内核构建](build.md) 的依赖和产物。跨架构构建前确认
`/proc/sys/fs/binfmt_misc/qemu-arm` 已启用。

启动前缀是**你自己的原厂 eMMC user 区备份的前 124MiB**，不是 boot0/boot1。
先完成 [Android 备份校验](android-backup.md)，再从备份文件提取该范围。
其中的 U-Boot、Trust、resource 等保持原厂内容，镜像生成器只改 MBR 与 kernel 区。
仓库不分发原厂二进制，也不提供包含个人账号的现成根文件系统。

## 构建根文件系统

```sh
bash scripts/build.sh
sudo bash scripts/build_rootfs.sh \
  "$PWD/build/rootfs" \
  "$PWD/build/emb3533-7.3.1-modules.tar.gz" \
  "$HOME/.ssh/id_ed25519.pub"
```

最后一个参数必须是自己的 SSH **公钥**，不能传私钥。输出目录必须尚不存在。
可通过 `DEBIAN_MIRROR` 指定 Debian 镜像源，软件包签名检查保持开启。

构建包含 trixie-updates 与 security 的全量包升级，未禁用软件包签名检查。
系统创建 `debian` 用户，使用公钥登录并提供免密 sudo；root 和用户密码保持锁定，
没有本地控制台默认密码。配置了 OpenSSH、systemd、系统 D-Bus、有线 DHCP、随机数服务和静态 BusyBox，
以及 Wi-Fi 驱动所需的软件包和固件，但不预置 SSID 或密码。

第一次启动会生成机器标识和 SSH 主机密钥，并从新机器标识派生一个稳定、
本地管理的以太网 MAC，随后启动网络和 SSH。不要把已经启动、初始化过的根目录
重新打包成通用模板。

## 生成整卡文件

```sh
sudo python3 scripts/make_sd_image.py \
  --boot-prefix /path/to/your/vendor-prefix.bin \
  --rootfs build/rootfs \
  --zimage build/kernel-out/arch/arm/boot/zImage \
  --dtb build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dtb \
  build/emb3533-debian13-cli.img
```

生成器要求 TF DTB 中 eMMC 禁用，拒绝覆盖已有输出或向 `/dev` 写入。
它检查模板身份信息，创建新的 MBR 签名、PARTUUID、ext4 UUID，按 PARTUUID 设置
启动参数，生成 ext4 并执行只读文件系统检查。镜像根分区约 4.5GiB，不自动占满大卡。

输出包含稀疏 `.img` 文件和 `.img.json` 清单，清单记录布局、输入摘要与整卡摘要。
可用 `gzip -1` 或 `pigz` 压缩；传输后分别校验压缩文件摘要和解压后的整卡摘要。
至少需要一张标称 8GB 的卡。实际写卡前仍需核对读卡器身份、目标容量与整卡写后读回。

产物包含所选操作者的公钥和私有来源的原厂固件，是一次部署的个性化产物。
发布二进制前需要重新检查固件分发权限和部署身份；项目仓库只维护构建源码与方法。

## 安装模块时保护系统链接

Debian 使用 `/lib -> usr/lib`。不要把含顶层 `lib/` 的归档直接解压到 `/`，
否则可能把链接替换成目录，让动态加载器、SSH 和普通命令一起失效。

项目提供的安装工具只接受一个内核版本下的普通文件和目录，拒绝父目录、越界路径、
链接和已有版本，并固定写入目标根的 `usr/lib/modules`：

```sh
sudo python3 scripts/install_modules.py build/emb3533-7.3.1-modules.tar.gz /mounted/root
sudo chroot /mounted/root depmod -a 7.3.1-emb3533-power
```

该工具不决定目标存储；运行前应确认 `/mounted/root` 确实是预期系统。
回滚内核时保留旧版本模块。若系统链接已经损坏，从独立救援系统挂载根分区，
先检查目录内容和 `usr/lib` 的完整性，再恢复链接，不要覆盖或重装整个根目录。
