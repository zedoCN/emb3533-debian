# NORCO EMB-3533 Debian

让 NORCO EMB-3533 工控板从 **TF 卡运行原生 Debian**，保留板载 Android，用于命令行、脚本和小服务实验。

本项目提供板级设备树、内核补丁、构建与封装工具，以及实机适配经验。
目前面向 **EMB-3533 / RK3288（RK3288W）、2GB RAM、原厂 2023-03 Android 固件所带的 U-Boot 2014.10** 这一实测组合。
其他板卡版本和固件需要重新核对。

## 现在能做什么

截至 2026-11-06，实机运行 **Debian 13.7 armhf + Linux 7.3.1-emb3533**：

- 原厂 U-Boot 从 TF 启动，systemd 作为 PID 1，四核在线。
- 有线 DHCP、DNS、密钥 SSH、TF ext4 读写和匹配内核模块通过验证。
- Python、SQLite、临时 systemd 服务与局域网 HTTP 服务实测通过。
- 正常重启和断电上电均已验证；原 eMMC Android 保留。

当前配置通过 SSH 使用。HDMI/DRM、声音、媒体、CPU 调频和 idle **已关闭**；
USB、Wi-Fi、温控和长期负载尚未验收。软件关机能卸载文件系统，但仍需手动断开 12V。
完整支持范围见 [适配状态与验证](docs/status.md)。

## 从哪里开始

| 你的目标 | 文档 |
| --- | --- |
| 了解板卡、接口和 DEBUG 串口 | [硬件与调试连接](docs/hardware.md) |
| 编译内核、DTB 和匹配模块，生成 KRNL 文件 | [构建指南](docs/build.md) |
| 理解 TF 启动条件、安装边界和恢复路径 | [启动与恢复](docs/boot-and-recovery.md) |
| 排查黑屏、kexec、timer/DMA、init 和随机数问题 | [适配经验](docs/bringup-notes.md) |
| 高效提取原 Android 到私有服务器 | [Android eMMC 备份](docs/android-backup.md) |
| 确认哪些功能真的测过、下一步适合做什么 | [适配状态与验证](docs/status.md) |
| 修改项目或报告另一块板子的结果 | [贡献指南](CONTRIBUTING.md) |

## 构建入口

在 Linux 构建机安装依赖后运行：

```sh
sudo apt install gcc-arm-linux-gnueabihf make bc bison flex \
  libssl-dev libelf-dev cpio curl python3 device-tree-compiler patch xz-utils
bash scripts/build.sh
```

脚本固定内核版本和源码 SHA-256，输出在 `build/`，不会刷写设备。
后续封装命令和根文件系统要求见 [构建指南](docs/build.md)。

**这还不是开箱即用的整卡发行版。** 仓库不制作 Debian 根文件系统，也不分发
原厂 U-Boot、Trust、resource 或整卡镜像。仅运行构建脚本不会得到可直接写卡启动的完整系统。

## 项目结构

```text
board/       板级 DTS 与实测内核配置
patches/     当前内核需要的板级补丁
scripts/     Linux 构建、KRNL 封装及追加 DTB 工具
docs/        硬件、构建、启动、排障与备份文档
```

设备树已移除单台机器的 MAC；部署时需设置自己的网络身份。
原始备份、账号、密钥、芯片身份和未脱敏串口日志不进入本仓库。
代码许可见 [LICENSE](LICENSE)。
