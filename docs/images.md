# 制作 Debian 命令行 TF 镜像

第一版定位为 **EMB-3533 专用的无桌面底包**：刷卡、配置 SSH 公钥、启动后即可运行脚本和小服务。
底包不带部署者身份；主机名和 Wi-Fi 在首次启动时导入。当前内核不提供完整容器所需的
namespaces / overlayfs，不能据此承诺 Docker、桌面或媒体功能；见 [支持矩阵](status.md)。

工具生成 **7GiB TF 整卡文件**，使用项目内核、干净的 Debian 13 armhf 根系统，
以及部署者提供的原厂启动前缀。只生成文件，不识别或写入读卡器。
TF 文件不能直接刷到 eMMC；板载存储使用 [迁移流程](emmc-migration.md)。

## 使用镜像

1. 校验下载文件的 SHA-256，再写入至少标称 8GB 的 TF 卡并完成写后读回。
2. 重新插入读卡器，Mac / Windows 会看到 **EMBSETUP** 分区。把自己的 SSH **公钥**
   复制到里面，文件名为 `authorized_keys`，不带 `.txt`。不能放私钥。
3. 只用网线时无需其他设置。需要无线时，把分区内 `setup.json.example` 复制为
   `setup.json`，填写主机名、国家代码和 **2.4GHz WPA2** Wi-Fi。主机名必须是一个小写
   DNS 标签。首次启动只支持一个无线网络，更多网络可在登录后配置。
4. 安全弹出，插入板卡，接网线或使用已配置的 Wi-Fi，上电。首次启动会生成身份，
   并将 TF 根分区和 ext4 文件系统扩展到卡的可用空间。在路由器找到 DHCP 地址后，
   用 `ssh debian@地址` 和对应私钥登录；`debian` 可免密 sudo。

没有默认密码；root、密码与 keyboard-interactive 登录关闭，本地控制台也没有默认密码。
忘放公钥时不会开放默认账号口令：关机后把卡放回读卡器，补上公钥再启动即可。
设置文件必须通过完整验证才会导入，不执行配置分区中的脚本；错误输入保留供修正。

每次新安装生成独立 machine-id、SSH 主机密钥和稳定的本地管理有线 MAC。
成功导入后删除配置分区的 `authorized_keys` 和 `setup.json`，后续启动不再导入。
**删除文件不等于安全擦除闪存**；放过 Wi-Fi 密码的卡仍应当作私有介质。
密码在目标 ext4 上以 root/600 的 WPA PSK 配置保存，导入服务不打印凭据。

## 从源码构建

需要能通过 binfmt/QEMU 运行 armhf chroot 的 Linux 构建机：

```sh
sudo apt install debootstrap qemu-user-static binfmt-support openssh-client \
  e2fsprogs dosfstools mtools python3
```

同时准备 [内核构建](build.md) 依赖。确认 `/proc/sys/fs/binfmt_misc/qemu-arm` 已启用。
启动前缀是 **自己的原厂 eMMC user 区备份前 124MiB**，不是 boot0/boot1。
先完成 [Android 备份校验](android-backup.md)，再从备份文件提取；仓库不分发原厂二进制。

```sh
bash scripts/build.sh
sudo bash scripts/build_rootfs.sh \
  "$PWD/build/rootfs" "$PWD/build/emb3533-7.3.1-modules.tar.gz"
sudo python3 scripts/make_sd_image.py \
  --boot-prefix /path/to/your/vendor-prefix.bin \
  --rootfs build/rootfs \
  --zimage build/kernel-out/arch/arm/boot/zImage \
  --dtb build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dtb \
  build/emb3533-debian13-cli.img
```

根目录必须尚不存在。`DEBIAN_MIRROR` 可选择 Debian 镜像源，软件包签名检查保持开启。
构建会安装 trixie-updates / security 全量包更新，包含 systemd、D-Bus、OpenSSH、
有线 DHCP、随机数与校时服务、Python、静态 BusyBox、扩容工具、Wi-Fi 工具与匹配固件。
底包没有个人公钥、SSID、WPA 配置、机器 ID 或 SSH 主机密钥。

要生成某一次部署的文件，可给镜像生成器增加 `--authorized-keys /path/to/key.pub`，
公钥会放在配置分区。旧的 `build_rootfs.sh` 第三个公钥参数也保留：生成镜像时将它移到
配置分区，不留在根分区；通用底包省略这些参数。

## 分区和首次扩容

当前格式 `emb3533-tf-v2`：

| 区域 | 位置 / 用途 |
| --- | --- |
| 原厂启动前缀 | 前 124MiB；保留 U-Boot / Trust / resource 等，只替换 MBR 和 36MiB kernel 区 |
| p1：EMBSETUP | 128MiB 起、32MiB FAT16，供读卡器填写首次配置 |
| p2：DEBIANTF | LBA5177344 起的 ext4，初始约 4.5GiB；按新 PARTUUID 启动 |

生成器拒绝 `/dev` 输出、已有输出、带初始化身份的模板和启用 eMMC 的 TF DTB，
生成新磁盘签名与 ext4 UUID，对根文件系统执行只读检查。产物为 `.img` 与 `.img.json`，
清单记录布局、输入摘要、整卡摘要及硬件启动验收标记。

扩容服务从当前根的 MAJ:MIN 识别设备，限定 **SD 类型、p2、预期 MBR 签名 / 布局和 ext4 UUID**。
不自动扩容 eMMC；不改分区起点、FAT 大小或原厂固件。首次改动前保留原 MBR，随后使用
[growpart](https://manpages.debian.org/trixie/cloud-guest-utils/growpart.1.en.html) 扩分区和
[resize2fs](https://manpages.debian.org/trixie/e2fsprogs/resize2fs.8.en.html) 扩 ext4。
工具可能规范化分区表的旧 CHS 字段；引导代码、磁盘签名与 LBA 起点保持不变。
失败不写成功标记；下次启动重试，可用 `journalctl -u emb3533-grow-root` 检查。

扩容状态：`/var/lib/emb3533/root-expanded`；导入状态：`/var/lib/emb3533/initialized`。
配置导入问题用 `journalctl -u emb3533-first-boot` 查看。不要直接删除标记来重复部署正在使用的机器。
旧 v1 单 p1 镜像不自动转换成 v2，仍可按原布局使用；新版工具只生成 v2。

## 打包与验收

```sh
gzip -1 -k build/emb3533-debian13-cli.img
sha256sum build/emb3533-debian13-cli.img.gz > build/emb3533-debian13-cli.img.gz.sha256
```

传输后分别核对压缩文件和完整解压内容的摘要。当前 v2 流程已通过实卡首次冷启动、
公钥导入、256GB 卡自动扩容、SSH、基础服务和正常重启验证；重启后机器身份保持不变。
本轮首次配置使用公钥加有线 DHCP，无线扫描通过，首次 Wi-Fi 配置认证仍待实卡验收。
换用新的镜像内容、内核或板卡配置时，需要重新完成对应产物的写卡与启动验证。

公开发布前还需检查原厂固件是否可分发。现阶段项目维护构建源码与方法，候选二进制私有保存。
新部署不要直接复制使用中的 eMMC 系统，否则会把账号、主机密钥和网络身份一起带走。

### macOS 自动挂载与写后校验

macOS 可能在写卡结束后自动挂载 EMBSETUP，并创建 `.fseventsd` 等元数据，改变 FAT 扇区。
给部署副本加入公钥也会改变它与通用底包之间的摘要；分别保留原始文件和部署副本的摘要。
写卡工具应在完整回读校验结束前阻止自动挂载。若已经出现摘要差异，先停止并定位：
引导区和 Linux 系统区需要逐字节匹配，FAT 需要只读文件系统检查和导入文件内容校验。
差异未经定位前，不重写或宣称校验成功。

## 软件更新与恢复

Debian 软件包按常规 APT 更新；自定义 KRNL 内核需要匹配的 DTB、模块与封装，
不能靠普通 APT 内核包替换。内核升级前保留已知可用的内核、模块和独立 TF 救援入口，
先试启动再持久化，见 [启动与恢复](boot-and-recovery.md)。当前没有自动 A/B 回滚功能。

Debian 使用 `/lib -> usr/lib`。不要把含顶层 `lib/` 的归档直接解压到 `/`，
项目安装工具只接受一个版本下的普通文件和目录，固定安装到 `usr/lib/modules`，
拒绝越界、链接、顶层父目录和已有版本：

```sh
sudo python3 scripts/install_modules.py build/emb3533-7.3.1-modules.tar.gz /mounted/root
sudo chroot /mounted/root depmod -a 7.3.1-emb3533-power
```

先确认目标挂载点。系统链接损坏时，从独立救援系统检查并恢复链接；不要覆盖整个根目录。
