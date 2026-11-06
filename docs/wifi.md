# 板载 Wi-Fi 与有线共存

## 硬件与配置

板载 RTL8188EU 是 **2.4GHz 802.11n USB 网卡**，经 7口 Hub 接在 RK3288 的
USB host1（`0xff540000`）上。它不能连接仅提供 5GHz 的网络；双频同名网络可使用 2.4GHz。

设备树启用 `usbphy` 与 `usb_host1`，并按原厂配置将 Hub 复位脚 GPIO0_B6 设为高电平。
其他 USB host 和 OTG 不随之启用，因此不能据此宣称所有 USB 口都已适配。

内核配置使用 `CONFIG_RTL8XXXU=m`，依赖 mac80211/cfg80211 与对应固件。
驱动来自同版本 Linux 上游源码；当前配置为模块，随匹配内核的模块包构建和安装。
公开配置已纳入该选项，完整构建流程仍以 [构建指南](build.md) 的验证边界为准。

## 准备根文件系统

APT 源启用 Debian `non-free-firmware` 组件，保留签名校验，然后安装：

```sh
sudo apt install iw wpasupplicant firmware-realtek wireless-regdb usbutils
```

固件为 `rtlwifi/rtl8188eufw.bin`；匹配模块安装及 `depmod` 后，由设备识别自动加载。

本项目使用上游内核签名证书，应选择上游签名的监管数据库，保留签名校验：

```sh
sudo update-alternatives --set regulatory.db /lib/firmware/regulatory.db-upstream
```

若继续使用 Debian 重新签名的数据库，上游内核可能报告签名无效并退回默认监管规则。
先确认 Hub、USB ID `0bda:8179`、无线接口和固件加载，再配置网络：

```sh
lsusb
iw dev
sudo ip link set wlan0 up
sudo iw dev wlan0 scan
```

项目使用 `net.ifnames=0`，验证接口名为 `wlan0`；如果调整命名策略，应替换下面的接口名。

## 开机自动连接

在目标机安全生成 `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf`，所有者为 root、权限600。
内容包括自己的 SSID、PSK、`ctrl_interface=/run/wpa_supplicant` 和 `update_config=0`，
国家码按所在地设置。不要把密码放进命令行、日志或公开仓库；SSID/PSK 是部署配置，不是板级源码。

使用 ifupdown 时，确认 `/etc/network/interfaces` 包含：

```text
source /etc/network/interfaces.d/*
```

在 `/etc/network/interfaces.d/wlan0` 配置：

```text
allow-hotplug wlan0
iface wlan0 inet dhcp
    wpa-conf /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
    metric 600
    pre-up /sbin/sysctl -q -w net.ipv6.conf.wlan0.accept_ra=0
```

这套配置验证的是 IPv4：无线默认路由使用较高 metric，使有线优先；无线暂不接收 IPv6 RA。
同名配置文件可能已经存在，修改前先读取并保留原配置，不覆盖其他网络管理器的设置。

在已有 `iface eth0 inet dhcp` 段添加：

```text
    pre-up /sbin/sysctl -q -w net.ipv4.conf.eth0.ignore_routes_with_linkdown=1
```

该设置让查路由时忽略失去链路的有线路由，避免遗留的高优先级默认路由挡住 Wi-Fi。
验证中通过管理命令将链路置为 down 测试了这条路径；物理拔线时延尚未测量。

## 验证顺序

1. `wpa_cli -i wlan0 status` 应显示 `wpa_state=COMPLETED`，随后得到 DHCP 地址。
2. 保持有线主路由，用绑定 `wlan0` 的 ping、DNS UDP 和 HTTPS 验证无线流量。
   只在双网卡环境中访问网页，不能证明流量经过无线。
3. 正常重启，核对自动识别、认证和 DHCP，再建立新的无线地址 SSH 连接。
4. 需要验证纯无线时，先建立已核对主机密钥的无线入口，并设置独立的有线自动恢复任务，
   再临时停用有线，确认无线 SSH 和 HTTPS；结束后恢复有线并取消恢复任务。

可使用以下命令检查基础状态；网关地址需替换为自己的值：

```sh
sudo iw dev wlan0 link
ip -4 route
ping -I wlan0 -c 5 你的网关地址
curl --interface wlan0 -4 --noproxy '*' --fail https://mirrors.ustc.edu.cn/debian/README
```

已验证识别、扫描、WPA2、IPv4 DHCP、DNS、HTTPS、有线共存、正常重启自动连接和纯无线 SSH。
协商速率不代表实际吞吐量；长期传输、AP模式、IPv6和这套新 Wi-Fi 配置的物理冷启动尚未验收。
