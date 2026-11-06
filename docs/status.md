# 支持矩阵

本页描述项目配置的支持范围和验证条件，不记录某台设备的日常运行状态。
验证基线为 **EMB-3533、2GB RAM、原厂 U-Boot 2014.10、Linux 7.3.1、Debian 13 armhf**。
其他内存版本、固件和设备树改动需要重新验证；硬件信息见 [硬件说明](hardware.md)。

## 启动与存储

| 能力 | 验证范围 |
| --- | --- |
| TF 启动 | 原厂 U-Boot 加载 KRNL，追加 DTB，直接挂 TF ext4 根；正常重启、断电上电通过 |
| eMMC 独立启动 | 保留原厂引导固件，追加启用 eMMC 的 DTB，按 PARTUUID 挂根；无 TF 正常重启、断电上电通过 |
| TF / eMMC 文件系统 | 根挂载、文件写入/fsync/回读、SQLite 通过；迁移后的文件 checksum 与离线 e2fsck 通过 |
| eMMC 总线 | 8 位、50MHz、VCC 3.3V / VQMMC 1.8V；未验收 HS200 或 DDR 提速 |
| Android 备份 | user/boot0/boot1 的源摘要与服务端完整解压长度、摘要一致；未做刷回启动验证 |
| 原 Android 保留 | 适用于不写 eMMC 的 TF 部署；eMMC 迁移会替换 Android，不能再通过取 TF 恢复 |

## 命令行功能

| 能力 | 验证范围 |
| --- | --- |
| 原生 systemd | PID 1 为 systemd，基础服务可用 |
| 四核 SMP | CPU0–3 在线，四个进程分别绑定计算，结果一致 |
| 有线网络 | DHCP、DNS、密钥 SSH、局域网另一台机器直连 HTTP 200 |
| 基础应用 | Python、SQLite、临时 systemd 服务运行通过 |
| 内核模块 | 匹配模块安装、vermagic 比对与 algif_hash 加载/卸载通过 |
| 随机数 | 配合 jitterentropy-rngd 独立启动，不依赖固定 DT 种子 |
| Debian 升级 | Debian 12 → 13 的升级、dpkg/依赖检查和重启通过 |

## 限制与待完成项

| 功能 | 状态 |
| --- | --- |
| HDMI/DRM、声音、媒体 | 配置关闭，提供 SSH 命令行用途 |
| CPU 调频 / idle | 配置关闭，厂商内核最高频率不能代表此配置的性能 |
| USB / Wi-Fi | 板级接口与联网未验收，编译出模块不等于可用 |
| 温控、长期满载 | 未验收，短时功能测试不能证明长期稳定性 |
| PMIC 软件切电 | 未完成；文件系统卸载后不切电，随后可能出现 RCU 停机警告，需手动断 12V |
| 完整安装体验 | 未提供通用整卡或 eMMC 写入安装器 |
| 全新构建环境复现 | 内核与模块已构建验证；公开构建脚本的完整全新环境复现仍待完成 |

TF 与 eMMC 的公开 DTS 不携带设备专属 MAC；实际部署需提供自己的网络配置。
原始设备回执与日志不公开，仓库保留复用所需的配置、方法与结论。

历史故障与设计原因见 [适配经验](bringup-notes.md)，迁移顺序见 [eMMC 指南](emmc-migration.md)。
