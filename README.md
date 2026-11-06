# NORCO EMB-3533 Debian

NORCO EMB-3533 / RK3288 工控板的原生 Debian 命令行适配，面向脚本和小服务。
支持从 **TF 卡或板载 eMMC** 启动，提供板级设备树、内核补丁、构建与封装工具，以及适配经验。

适配针对 **RK3288 / RK3288W、2GB RAM、原厂 2023-03 Android 固件所带的 U-Boot 2014.10**。
其他板卡版本和固件需核对电气配置与启动布局。

## 支持范围

- 构建基线为 Linux **7.3.1**；Debian **13 armhf** 命令行环境已验证。
- TF 与 eMMC 启动均已验证正常重启和断电上电；使用 systemd、四核、有线网络与 SSH。
- 支持 TF/eMMC ext4 根文件系统，匹配内核模块，以及 Python、SQLite 和基础网络服务。
- HDMI/DRM、声音、媒体、CPU 调频和 idle 在项目配置中关闭；USB、Wi-Fi、温控和长期负载尚未验收。
- 软件关机可卸载文件系统，但 PMIC 切电未完成，仍需手动断开 12V。

详细条件和验证边界见 [支持矩阵](docs/status.md)。

## 选择启动方案

| 方案 | 设备树 | 原 Android 与恢复方式 |
| --- | --- | --- |
| TF 启动 | `rk3288-emb3533.dts` | eMMC 控制器禁用；不写 eMMC 时可保留 Android |
| eMMC 启动 | `rk3288-emb3533-emmc.dts` | 启用 eMMC；迁移会替换 Android，先做私有备份，保留 TF 救援系统 |

构建会输出两种 DTB，不会自动选择目标磁盘或刷写设备。

## 文档入口

| 你的目标 | 文档 |
| --- | --- |
| 了解板卡、接口和 DEBUG 串口 | [硬件与调试连接](docs/hardware.md) |
| 编译内核、DTB、匹配模块，生成 KRNL 文件 | [构建指南](docs/build.md) |
| 理解启动链路、更新条件与恢复路径 | [启动与恢复](docs/boot-and-recovery.md) |
| 把 TF 上的 Debian 迁到板载存储 | [迁移到 eMMC](docs/emmc-migration.md) |
| 排查 kexec、timer/DMA、init 和随机数问题 | [适配经验](docs/bringup-notes.md) |
| 提取原 Android 并保存到私有服务器 | [Android eMMC 备份](docs/android-backup.md) |
| 查看验证范围、未完成项或贡献代码 | [支持矩阵](docs/status.md) · [贡献指南](CONTRIBUTING.md) |

## 构建入口

在 Linux 构建机安装依赖后运行：

```sh
sudo apt install gcc-arm-linux-gnueabihf make bc bison flex \
  libssl-dev libelf-dev cpio curl python3 device-tree-compiler patch xz-utils
bash scripts/build.sh
```

脚本固定源码版本和 SHA-256，产物输出到 `build/`。封装与部署条件见 [构建指南](docs/build.md)。

仓库尚不提供完整整卡发行版或通用迁移安装器：Debian 根文件系统和原厂启动固件需自行准备。
仅运行构建脚本不会得到可直接整卡写入的完整系统。

## 项目结构

```text
board/       TF 与 eMMC 板级 DTS、实测内核配置
patches/     板级内核补丁
scripts/     Linux 构建、KRNL 封装和追加 DTB 工具
docs/        硬件、构建、启动、迁移与排障文档
tests/       启动文件封装工具测试
```

公开 DTS 不包含单台机器的 MAC，部署时需设置自己的网络身份。
设备台账、备份、账号、密钥、芯片身份和原始串口日志保存在私有资料中。
代码许可见 [LICENSE](LICENSE)。
