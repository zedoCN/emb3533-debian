# 启动、更新与恢复

## 启动链路

```mermaid
flowchart LR
    A[原厂 U-Boot / Trust] --> B[原厂 resource 初始化]
    B --> C[目标存储 kernel 区：KRNL]
    C --> D[zImage + 追加的板级 DTB]
    D --> E[TF 或 eMMC ext4 根文件系统]
    E --> F[systemd → 有线网络与 SSH]
```

项目主线配置直接挂载所选根分区，不依赖 initramfs。
原厂 U-Boot 仍会读取保留的 ramdisk，但追加 DTB 不传入 initrd 地址，Linux 不使用它。
原厂 resource 中的 DTB 给 U-Boot 做硬件初始化；Linux 使用内核末尾追加的主线 DTB。

仓库没有提供原厂启动固件或整卡安装器。新做一张卡时，仍需取得自己设备的启动资料、
确认布局并准备 Debian armhf 根文件系统，不能把单个 `emb3533-kernel.img` 当成整卡镜像写入。

## 已观察到的布局

以下是**验证过的原厂布局中的物理字节偏移**，用于理解日志和备份范围，
并非所有 EMB-3533 / RK3288 设备的通用刷写参数。

| 区域 | 物理起点 | 区域容量 | 用途 |
| --- | --- | --- | --- |
| resource | 20MiB | 16MiB | 保留原厂内容 |
| kernel | 36MiB | 24MiB | KRNL 封装的 zImage + DTB |
| boot / ramdisk | 60MiB | 32MiB | 保留既有恢复探测环境，主线不依赖它 |

厂商 parameter 的逻辑扇区偏移可能包含额外基址，不能直接当成物理偏移。
写入范围须结合自己设备的实际头信息、分区起点和备份确认。
SD 卡需要普通分区表；不能因为厂商内核能解析 eMMC 的 Rockchip 分区，就假定无 MBR 的 SD 也能生成分区节点。

## 更新顺序

系统软件包与板级内核分别维护：APT 管理 Debian 用户空间；本项目内核由源码构建及独立封装。
安装通用 Debian 内核包不等于替换了本板的 KRNL 启动文件。

1. 记录当前版本、启动参数和根分区身份；保存匹配的根文件系统、启动区与模块恢复点。
2. 在独立构建目录制作候选内核，先用串口和 RAM kexec 验证，不改默认启动区。
3. 确认四核、挂根、网络、随机数与基础工作负载后，再安装匹配模块并更新目标存储的 kernel 区。
4. 写入前重新核对 SD/MMC 类型、身份、容量、分区起点、旧内容摘要与写入边界；写后同步并完整读回核对摘要。
5. 分别验证正常重启和断电上电，最后清理临时服务、种子和诊断入口。

kexec 的装载范围是本板重要限制，见 [适配经验](bringup-notes.md#arm-kexec-在-bye-后无输出)。
RAM 试启动通过不代表原厂引导器能加载同一产物，正常重启也不能替代断电上电验证。

Debian 大版本升级前先模拟升级并检查 SSH/网络依赖，保留签名校验。
升级应有可回查的后台任务、日志和退出码；D-Bus 重启造成前端断线时，先查原任务，不重复启动 APT。
系统版本与功能范围见 [支持矩阵](status.md)。

## 启动失败如何定位

先录 DEBUG 串口，按阶段判断：

| 看到的现象 | 优先检查 |
| --- | --- |
| Mac 没有新增 USB / 串口 | DEBUG 与 OTG 是否接错、是否为数据线、USB 枚举 |
| 无 U-Boot 日志 | 板卡 12V、串口参数、端口占用 |
| U-Boot 有输出，内核无输出 | KRNL 格式、加载/解压位置、追加 DTB、早期 UART |
| external abort / panic | timer、DMA 实际寄存器地址与对应调用栈 |
| BusyBox 应急 shell | 根分区是否存在、systemd 文件与 switch_root 路径 |
| systemd 已启动但 SSH 未出现 | 随机数初始化、DHCP、MAC/租约、SSH 服务与主机密钥 |

四个企鹅、BusyBox 的 Debian 版本横幅、链路灯闪烁或 chroot 中的 SSH，
都不能单独证明原生 Debian 完成启动。应同时确认 PID 1、根挂载和真实服务路径。

## 恢复边界

- 只在 TF 部署、eMMC Android 未被替换时：断开 12V 和可能供电的 OTG USB，取出 TF，再接回 12V，可回到原 Android。
- 已迁到 eMMC 时：TF 应保留为 Debian 救援系统；恢复 Android 需要刷回私有备份，取出 TF 不会恢复。
- TF 内核失败时，用读卡器恢复自己保存的启动区，或从 Android 的受控维护入口操作；
  不假定 U-Boot 一定带有 `mmc` 读写命令，验证用精简引导器没有这些命令。
- 跨 Debian 大版本回退需配套根文件系统和模块，不能只把 Debian 13 的内核换回厂商 4.4。
- 软件关机目前不切电。确认文件系统卸载或只读后再手动断 12V；停机后的 RCU 警告属于已知未完成项。

备份方法已经验证普通 eMMC 区的提取和摘要校验，尚未完成刷回 Android 启动演练；
备份完整性与恢复可用性应分开判断，详见 [Android 备份](android-backup.md)。
eMMC 的准备与分阶段安装顺序见 [迁移指南](emmc-migration.md)。
