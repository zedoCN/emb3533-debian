# 温度、RTC 与 CPU 调频

当前配置使用 Linux `7.3.1-emb3533-power`，提供 CPU/GPU 温度读取、RTC 和
126–1608MHz 的共享 CPU 调频策略，默认 governor 为 `schedutil`。
按需使用高频、空闲降频，持续负载由温控限制；不依赖受保护 efuse 的电压分档。
旧 r3 镜像仍使用 816MHz 上限，新频率配置从 r4 候选开始。

## 时钟与温度传感器

PCF8563 位于 **I2C4 / ff160000、地址 0x51**。它既是 RTC，也通过 CLKOUT
提供 TSADC 所需的 `xin32k`。只声明一个 32768Hz 的 `fixed-clock` 会让软件时钟树
显示频率，却不会打开实际输出，结果是传感器注册成功、数据寄存器仍为 0。

DTS 将 RTC 声明为时钟提供者，并让 TSADC 的 assigned-clocks 显式引用它。
这样会等待 RTC 驱动注册，再设置采样时钟，避免模块晚加载时用到孤立的父时钟。
`CONFIG_RTC_DRV_PCF8563=m` 的匹配模块必须随根文件系统安装。

CPU/GPU 传感器分别使用通道 1/2。软件被动降温阈值沿用上游 70/75°C，
软件临界温度为 90°C；硬件 TSHUT 配置为 95°C、CRU 复位模式，OTP 引脚保持
原厂 GPIO 配置。温度读数与手动 cooling-device 限频已验证，未通过把芯片加热到
临界温度来验证热复位，更不能把它当成已适配 PMIC 切电。

## CPU 电压和频率

CPU 的实际供电是 I2C0 地址 0x40 的 **SYR827**，由 FAN53555 驱动支持，
不是 ACT8846 的 `REG3/vdd_log`。`cpu-supply` 必须连接到这个独立电源。
下表使用原厂 L0 表的保守电压：

| 频率 MHz | 电压 mV |
| --- | --- |
| 126、216 | 950 |
| 408、600、696 | 975 |
| 816 | 1075 |
| 1008 | 1150 |
| 1200 | 1200 |
| 1416 | 1300 |
| 1512、1608 | 1350 |

默认 governor 为 `schedutil`；四个 CPU 共用 `policy0`。
OPP 表缩减后也要同步修改 cooling-map，不能保留超出可用档数的最大 cooling state。
当前共有十一档；cooling-map 使用实际可用档数，不固定为旧版六档。
不要照搬旧版本中 cooling state 与频率的对应关系。

可通过以下接口检查实际状态：

```sh
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies
cat /sys/devices/system/cpu/cpufreq/policy0/stats/time_in_state
for zone in /sys/class/thermal/thermal_zone*; do
  cat "$zone/type" "$zone/temp"
done
```

温度单位为毫摄氏度，频率接口单位为 kHz。某次 SSH 操作时读到最高频率，
不代表 CPU 一直满速；应结合 `time_in_state` 比较空闲和负载阶段。

## 验证边界

验证包括逐档频率/电压回读、cooling-device 限频，以及四核和约 512MiB 内存的
约 9 分钟计算校验，期间执行 eMMC 写入/fsync/回读和无线 HTTPS。
这属于有界功能与稳定性验证，不能代表数天满载、所有环境温度或所有板卡批次。
后续已逐档核对新增频率/电压，四核、256MiB 已知摘要与整数结果校验通过。
1.2GHz 热机持续五分钟，最高约 65.4°C。固定 1.608GHz 与热机 1.416GHz 的试验
触到人为设置的 70°C 停止线后结束，不能视为持续高频稳定证明。

按需 1.608GHz 模式通过三轮十秒短负载和四分钟持续负载：短负载均到最高频，
持续负载在 1.2–1.608GHz 间自动调整，峰值约 72.5°C；独立读取 cooling state 确认
温控介入，空闲最低见 126MHz。默认 eMMC 正常重启、升降频、计算和读写检查通过。
这些温度只属于当时环境和散热条件，不是其它板卡的保证值；新配置的物理冷启动与长期负载仍待验证。

主动风扇可以改善温度限制，但不能替代高频计算正确性、供电和持续负载验证。
没有测量墙插功耗，不能仅凭降频统计给出节电百分比。

原厂 Trust 固件没有正常返回 PSCI 版本信息。已有 CPU 上线和重启路径可用，
不能据此推导 `CPU_SUSPEND` 能力；当前没有添加新的 PSCI 深度 idle 状态或系统挂起支持。
扩展频率、改电压或增加休眠状态时，应先保留可独立启动的恢复系统，使用 RAM 试验。
