# 支持矩阵

本页描述项目配置的支持范围和验证条件，不记录某台设备的日常运行状态。
验证基线为 **EMB-3533、2GB RAM、原厂 U-Boot 2014.10、Linux 7.3.1、Debian 13 armhf**。
其他内存版本、固件和设备树改动需要重新验证；硬件信息见 [硬件说明](hardware.md)。

原 `7.3.1-emb3533` 与 816MHz 上限的 `7.3.1-emb3533-power` 基线均通过 TF/eMMC 冷启动；
r3 的 v2 TF 首次配置、扩容与重启通过。新版 1.608GHz 配置通过 eMMC 正常重启和自动调频测试，
r4 整卡尚未完成新的写卡冷启动验收。下表的冷启动结果属于前述基线，不能直接继承到新版镜像。

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
| 板载 Wi-Fi | RTL8188EU/rtl8xxxu，2.4GHz；识别/扫描/WPA2/DHCP/DNS/HTTPS与正常重启自动连接通过 |
| 无线独立访问 | 临时停用以太网后无线 SSH、HTTPS通过；有线链路 down 且地址保留时，路由可选择无线 |
| USB 大容量存储 | 当前已启用的一路外部接口，USB-SATA SSD 枚举、ext4 挂载、256MiB 写入/fsync/回读摘要通过；USB 2.0 / usb-storage，非 UAS |
| 内部 USB 链路 | USB host1 → 7口 Hub → RTL8188EU 枚举和运行通过 |
| 基础应用 | Python、SQLite、临时 systemd 服务运行通过 |
| 内核模块 | 匹配模块安装、vermagic 比对与 algif_hash 加载/卸载通过 |
| 随机数 | 配合 jitterentropy-rngd 独立启动，不依赖固定 DT 种子 |
| Debian 升级 | Debian 12 → 13 的升级、dpkg/依赖检查和重启通过 |

## 限制与待完成项

| 功能 | 状态 |
| --- | --- |
| HDMI/DRM、声音、媒体 | 配置关闭，提供 SSH 命令行用途 |
| CPU 调频 | 126–1608MHz、schedutil；逐档电压/频率、短负载升频、持续负载自动温控降频与正常重启通过，详见[温控说明](power-and-thermal.md) |
| 深度 idle / 挂起 | 未启用新的 PSCI 休眠状态；固件完整能力未验证 |
| 其余 USB / OTG | 未做逐口插拔或 OTG 主从切换验证 |
| 容器与命名空间 | 当前 NAMESPACES、OVERLAY_FS 未启用；不能按标准 Docker/Podman 容器环境使用 |
| Wi-Fi 扩展验证 | 新配置的冷启动驱动识别通过；目标SSID下的冷启动自动联网、实际拔线切换时延、IPv6、AP模式与长期传输未验收 |
| 温度、RTC | PCF8563 CLKOUT 驱动 TSADC，CPU/GPU 温度可读；RTC 校时通过；未做临界温度触发测试 |
| 有界负载 | 四核、约512MiB计算校验约9分钟，包含eMMC fsync/回读和Wi-Fi HTTPS；不能证明长期稳定性 |
| PMIC 软件切电 | 未完成；文件系统卸载后不切电，随后可能出现 RCU 停机警告，需手动断 12V |
| 镜像构建 | v2 实卡冷启动、公钥导入、自动扩容、SSH、重启后身份保持、D-Bus/临时服务、Python/SQLite/HTTPS、匹配模块、SD/USB读写通过；本轮无线只验扫描，首次Wi-Fi配置认证仍待验收 |
| eMMC 安装器 | 仍使用身份绑定的迁移流程，未提供通用自动安装器 |
| 全新构建环境复现 | 内核与模块已构建验证；公开构建脚本的完整全新环境复现仍待完成 |

TF 与 eMMC 的公开 DTS 不携带设备专属 MAC；实际部署需提供自己的网络配置。
原始设备回执与日志不公开，仓库保留复用所需的配置、方法与结论。

历史故障与设计原因见 [适配经验](bringup-notes.md)，迁移顺序见 [eMMC 指南](emmc-migration.md)。

Wi-Fi 的驱动、固件、网络配置与测试方法见 [Wi-Fi 指南](wifi.md)。

温度、供电、调频范围见 [温度与调频](power-and-thermal.md)；干净模板与镜像流程见 [镜像制作](images.md)。
