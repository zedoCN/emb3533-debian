# 硬件与调试连接

## 适用硬件

| 项目 | 已知信息 |
| --- | --- |
| 板卡 | NORCO 华北工控 EMB-3533 |
| SoC | RK3288 / RK3288W，四核 Cortex-A17，ARMv7 32 位 |
| 内存 | 2GB，Linux 可见约 1.9GiB |
| 板载存储 | 标称 16GB eMMC，可部署 Debian |
| 根文件系统 | TF 或 eMMC，Debian armhf |
| 有线网络 | 千兆以太网，基础联网已验证 |
| USB | RK3288 原生 USB 2.0，最高 480Mbps；没有原生 USB 3.0 |
| Wi-Fi | RTL8188EU USB，2.4GHz，Debian 下已验证联网；不支持 5GHz |
| 原 Android | Android 7.1.2，固件构建日期 2023-03-03 |
| 原厂引导器 | `2014.10-RK3288-06-g37a5f47`，默认 `bootcmd=bootrk` |

旧厂商 4.4 内核曾报告最高 1608MHz；当前配置仅启用 126–816MHz 调频，
不能把旧频率或芯片标称参数当成此配置的性能。
接口外形和芯片规格也不代表项目内核已经支持全部扩展。
2023-03 是验证用 Android 固件日期，不是 U-Boot 的上游版本号。

厂家资料：[产品页](https://www.norco.com.cn/product_detail_363.html)、
[ARM Wiki](http://android1.norco.com.cn:7070/index.php/EMB-3533)。

RK3288 的 USB Host / OTG 均为 2.0，见 [瑞芯微数据手册](https://opensource.rock-chips.com/images/4/4e/Rockchip_RK3288_Datasheet_V2.2-20170301.pdf)。
项目已启用的 host1 经内部 Hub 连接 Wi-Fi 与一个已验证的外部 USB-SATA SSD 接口，
二者共享这条 USB 2.0 上行链路。升级内核不能把原生接口升级成 USB 3.0。

## DEBUG 与 OTG 是两个接口

厂家 [EMB-3533-COM 说明](http://android1.norco.com.cn:7070/index.php/EMB-3533-COM)
给出的 DEBUG 接口是**自带 USB 转串口的 Micro-USB**，直接用 USB 数据线连接电脑。
它与外露面板上的 OTG Micro-USB 分开；本板接 DEBUG 不需要另接 USB-TTL 裸线。

以厂家布局图正面朝上、LAN/HDMI/USB 位于下方为方向，DEBUG 在左上固定孔旁。
照片方向改变后位置也会改变，应结合丝印和厂家布局识别。

实机串口参数：**115200 波特率、8 数据位、无校验、1 停止位、无流控（8N1）**。
换用数据线后，Mac 枚举出 CH340（USB VID:PID `1a86:7523`），系统使用 AppleUSBCHCOM。
这是已验证的 Mac 环境结果；先检查 USB 是否枚举，再判断是否缺驱动。

在 Mac 上可以比较插线前后的串口列表：

```sh
ls /dev/cu.*
```

用串口终端打开实际新增的端口，再给板卡接通 12V，捕获从 U-Boot 开始的完整日志。
串口终端中设置上述 8N1 参数，不使用硬件或软件流控。
USB 桥可能在板卡 12V 断开时仍被 Mac 供电枚举，**看到串口不等于主板已上电**。
同一串口只由一个程序占用，避免录制器和交互终端抢读。

## 使用项目配置

日常入口是有线 SSH；HDMI/DRM 已关闭，显示器无信号本身不能证明启动失败。
先从 DHCP 租约、SSH 和串口判断启动阶段。网口链路灯闪烁只说明链路有活动。

TF 设备树禁用 eMMC，便于保留 Android；eMMC 变体启用板载控制器。
控制器探测顺序和块设备编号不能作为永久身份，应使用 PARTUUID 等稳定标识。
安装前见 [Android 备份](android-backup.md) 与 [eMMC 迁移](emmc-migration.md)。
板载无线连接方法见 [Wi-Fi 指南](wifi.md)。
