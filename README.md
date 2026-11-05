# NORCO EMB-3533 Debian

RK3288/RK3288W 工控板的原生 Debian 命令行适配记录、设备树和构建脚本。
适用于本次测试的 **EMB-3533、2GB RAM、原厂 2023-03 U-Boot**；其他板卡/固件未验证。

## 当前实机状态

- Debian 12.15 armhf 已在 TF 卡独立运行，原 eMMC Android 保留。
- Linux 6.12.115 已通过 RAM kexec 实测：原生 systemd、四核、有线 DHCP/DNS/SSH、TF ext4 读写、Python/SQLite 和局域网 HTTP 服务。
- Linux 7.3.1 与 Debian 13.7 正在适配，尚不能宣称可直接安装。
- HDMI、Wi-Fi、USB 扩展、调频、温控及长期稳定性尚未验收。

## 仓库内容

- `board/`：本板实验设备树，已移除单台设备 MAC 等个人配置。
- `patches/`：原厂固件下主线内核访问 timer6/7 异常的板级补丁。
- `scripts/`：固定源码版本的构建与 Rockchip KRNL 封装工具。
- `docs/`：启动限制、实机验证与恢复方法。

不包含原厂固件、设备备份、私钥、账号或个人网络配置。
这是适配项目，不是对所有 RK3288 盒子通用的镜像。

## 构建

构建机使用 Linux，安装 `gcc-arm-linux-gnueabihf make bc bison flex libssl-dev libelf-dev cpio curl python3`。
运行 `bash scripts/build.sh`；输出在 `build/`。构建不会刷写任何设备。

## 启动要点

旧 Rockchip U-Boot 使用 KRNL 封装，不能用 Android-v0 boot.img 代替。
主线的 secure DMA 地址与本机原厂 DT 不同；设备树使用原厂非安全别名。
ARM kexec-tools 旧版本需要显式限制装载范围以避开 multi_v7 解压目标。
详见 [适配状态](docs/status.md)。
