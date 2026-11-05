# NORCO EMB-3533 Debian

RK3288/RK3288W 工控板的原生 Debian 命令行适配记录、设备树和构建脚本。
适用于本次测试的 **EMB-3533、2GB RAM、原厂 2023-03 U-Boot**；其他板卡/固件未验证。

## 当前实机状态

- Debian 13.7 armhf 已由 12.15 升级，在 TF 卡独立运行，原 eMMC Android 保留。
- Linux 6.12.115 已通过 RAM kexec 实测：原生 systemd、四核、有线 DHCP/DNS/SSH、TF ext4 读写、Python/SQLite 和局域网 HTTP 服务。
- Linux 7.3.1 已通过四核 RAM 试启动，也已设为 TF 默认内核并通过原厂 U-Boot 正常重启；完整匹配模块已安装，模块加载通过。
- Python 3.13.5、systemd 257.13；升级结束的软件包检查通过，SSH 与有线网络正常，无失败服务。
- HDMI 图形输出、声音、媒体、CPU 调频/idle 当前关闭；Wi-Fi、USB 板级扩展、温控及长期稳定性尚未验收。
- 升级后实际断电上电通过：四核、SSH自动恢复、TF读写、Python/SQLite/DNS和局域网HTTP服务验证成功，无失败服务。
- 软件关机目前不会切断板卡电源，需手动断12V；详细边界见 [验证记录](docs/status.md)。

## 仓库内容

- `board/`：本板实验设备树，已移除单台设备 MAC 等个人配置。
- `patches/`：原厂固件下主线内核访问 timer6/7 异常的板级补丁。
- `scripts/`：固定源码版本的构建与 Rockchip KRNL 封装工具。
- `docs/`：启动限制、实机验证与恢复方法。

不包含原厂固件、设备备份、私钥、账号或个人网络配置。
这是适配项目，不是对所有 RK3288 盒子通用的镜像。

## 构建

构建机使用 Linux，安装 `gcc-arm-linux-gnueabihf make bc bison flex libssl-dev libelf-dev cpio curl python3 device-tree-compiler`。
运行 `bash scripts/build.sh`；内核、DTB 和匹配的模块包输出在 `build/`。构建不会刷写任何设备。
`board/kernel.config` 从实测 7.3.1 配置导出；已验证还原后与实机配置一致。

`scripts/make_kernel_image.py` 将 DTB 追加到 zImage 后封装为 KRNL 文件，并要求显式指定根设备。
这一启动方式保留原厂 U-Boot/resource/ramdisk，引导主线内核直接挂载 TF ext4 根分区；
关键 MMC、供电、ext4 等驱动必须内置。它只生成文件，不会修改存储设备。
设备树不含单台机器 MAC；部署时应按自己的设备设置稳定 MAC 或 DHCP 配置。

生成供原厂引导器使用的内核文件，例如：

```sh
python3 scripts/make_kernel_image.py \
  build/kernel-out/arch/arm/boot/zImage \
  build/kernel-out/arch/arm/boot/dts/rockchip/rk3288-emb3533-trial.dtb \
  build/emb3533-kernel.img --root /dev/mmcblk0p1
```

TF 根文件系统需自行准备为 Debian armhf，安装 systemd、有线网络、OpenSSH 和
`jitterentropy-rngd`，配置自己的SSH密钥/网络，并安装匹配模块。构建脚本不制作根文件系统。
随机数服务应在首次独立启动前启用；不能把曾用于测试的固定随机种子写进永久镜像。

## 启动要点

旧 Rockchip U-Boot 使用 KRNL 封装，不能用 Android-v0 boot.img 代替。
主线的 secure DMA 地址与本机原厂 DT 不同；设备树使用原厂非安全别名。
ARM kexec-tools 旧版本需要显式限制装载范围以避开 multi_v7 解压目标。
详见 [适配状态](docs/status.md)。
