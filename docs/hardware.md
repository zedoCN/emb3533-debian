# 硬件与调试连接

## 实测对象

| 项目 | 已知信息 |
| --- | --- |
| 板卡 | NORCO 华北工控 EMB-3533 |
| SoC | RK3288 / RK3288W，四核 Cortex-A17，ARMv7 32 位 |
| 内存 | 2GB，Linux 可见约 1.9GiB |
| 板载存储 | 标称 16GB eMMC，保留原 Android |
| 实验系统存储 | TF 卡，Debian armhf 根文件系统 |
| 有线网络 | 千兆以太网，基础联网已验证 |
| Wi-Fi | 本机原系统识别为 RTL8188EU USB 设备，Debian 尚未联网验收 |
| 原 Android | Android 7.1.2，固件构建日期 2023-03-03 |
| 原厂引导器 | `2014.10-RK3288-06-g37a5f47`，默认 `bootcmd=bootrk` |

旧厂商 4.4 内核曾报告最高 1608MHz；当前主线配置关闭 CPU 调频，
不能把旧频率或芯片标称参数当成当前性能实测结果。
接口外形和芯片规格也不代表当前内核已经支持全部扩展。
2023-03 是本机 Android 固件日期，不是 U-Boot 的上游版本号。

厂家资料：[产品页](https://www.norco.com.cn/product_detail_363.html)、
[ARM Wiki](http://android1.norco.com.cn:7070/index.php/EMB-3533)。

## DEBUG 与 OTG 是两个接口

厂家 [EMB-3533-COM 说明](http://android1.norco.com.cn:7070/index.php/EMB-3533-COM)
给出的 DEBUG 接口是**自带 USB 转串口的 Micro-USB**，直接用 USB 数据线连接电脑。
它与外露面板上的 OTG Micro-USB 分开；本板接 DEBUG 不需要另接 USB-TTL 裸线。

以厂家布局图正面朝上、LAN/HDMI/USB 位于下方为方向，DEBUG 在左上固定孔旁。
照片方向改变后位置也会改变，应结合丝印和厂家布局识别。

实机串口参数：**115200 波特率、8 数据位、无校验、1 停止位、无流控（8N1）**。
换用数据线后，Mac 枚举出 CH340（USB VID:PID `1a86:7523`），系统使用 AppleUSBCHCOM。
这只是本机结果；先检查 USB 是否枚举，再判断是否缺驱动。

在 Mac 上可以比较插线前后的串口列表：

```sh
ls /dev/cu.*
```

用串口终端打开实际新增的端口，再给板卡接通 12V，捕获从 U-Boot 开始的完整日志。
串口终端中设置上述 8N1 参数，不使用硬件或软件流控。
USB 桥可能在板卡 12V 断开时仍被 Mac 供电枚举，**看到串口不等于主板已上电**。
同一串口只由一个程序占用，避免录制器和交互终端抢读。

## 使用当前配置

日常入口是有线 SSH；HDMI/DRM 已关闭，显示器无信号本身不能证明启动失败。
先从 DHCP 租约、SSH 和串口判断启动阶段。网口链路灯闪烁只说明链路有活动。

当前 DTS 禁用 eMMC，限制日常实验对原 Android 的影响。
临时启用 eMMC 会改变控制器探测顺序，不能继续假定原来的 `mmcblkN` 编号。
备份流程见 [Android eMMC 备份](android-backup.md)。
