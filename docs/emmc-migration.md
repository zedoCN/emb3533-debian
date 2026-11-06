# 从 TF 迁移到 eMMC

适用于已经能从 TF 启动 Debian、准备改为板载存储独立运行的 EMB-3533。
本流程会替换原 Android；先保存私有备份，并保留可启动的 TF 救援卡。
仓库提供 eMMC DTS 与封装工具，**未提供自动分区或写盘安装器**。

## 配置差异

[`rk3288-emb3533-emmc.dts`](../board/rk3288-emb3533-emmc.dts) 复用 TF 设备树，启用 eMMC：

- 总线宽度 8 位，最高 50MHz，不启用 HS200 / DDR 提速。
- VCC 使用 3.3V 的 `vcc_io`，VQMMC 使用 1.8V 的 `vcc_flash`。
- 引脚为 `emmc_clk`、`emmc_cmd`、`emmc_bus8`、`emmc_pwr`。
- TF 控制器仍可用；启动根由明确的 PARTUUID 选择。

以上电气参数针对支持矩阵中的板卡版本。公开 DTS 移除了单台设备 MAC，
部署时还需配置自己的网络身份。

## 分阶段迁移

### 1. 备份并确认源、目标

按 [Android 备份方法](android-backup.md) 保存 user/boot0/boot1，
核对服务端长度、原始摘要、压缩摘要和私有存储权限。
另留 TF 的根文件系统、启动区和模块恢复点。

先在 RAM 中启用 eMMC，继续使用 TF 根。检查 MMC/SD 类型、容量、芯片身份、根设备，
并确认 eMMC 未挂载且只读；不能按 `mmcblk0` / `mmcblk1` 名字盲选。
用自己的原厂启动区备份比对读取结果，再决定写入范围。

### 2. 保留引导固件，准备根分区

验证过的方式保留 U-Boot、Trust、resource、boot 和 eMMC 硬件启动区，
在原 userdata 范围准备 ext4 根分区，以兼容原厂 parameter 和引导器。
参考样本中 userdata 的物理起点为 **LBA 5177344（512 字节扇区）**，
此值需从目标设备实际 parameter 及基址重新确认，不能作为通用刷写参数。

主线内核需要能解析的分区表；该方案添加 MBR 根分区，设置非零且唯一的磁盘签名，
保留 IDB 和前方启动区域。不要把 256GB TF 的分区表或整卡镜像直接复制到 16GB eMMC。

格式化与复制前，再确认写入范围位于 userdata 内、目标未挂载、当前根仍在 SD。
先停止会改写数据的业务服务和自动升级任务，再复制稳定的系统文件。
复制可使用 `rsync -aHAXx --numeric-ids` 保留权限、ACL、扩展属性和硬链接，
排除 `/proc`、`/sys`、`/dev`、`/run`、临时目录及目标挂载目录。
随后创建必要的空运行目录，配置目标 fstab，并核对源、目标文件内容。
目标根卸载后执行离线文件系统检查。

### 3. 使用稳定根标识

MBR 根分区使用 `PARTUUID=xxxxxxxx-xx`，通过 `blkid` 查询实际值。
内核直接挂根使用 PARTUUID，目标 `/etc/fstab` 可使用 ext4 UUID。
使内核与 fstab 指向同一个已确认的目标分区。

设备编号与设备号都可能变化：同名 `mmcblk1p1` 在不同探测顺序下也可能得到不同 MAJ:MIN。
核对实际 sysfs、MMC 类型和分区标识，不从名字推算设备号。
封装命令见 [构建指南](build.md)。

### 4. 先验证根系统，再改默认 kernel

先用内核、eMMC DTB 和 PARTUUID 进行 RAM kexec，直接挂 eMMC 根，不改默认 kernel 区。
验证 systemd、四核、随机数、网络/SSH、eMMC fsync/回读、SQLite 与匹配模块。

通过后，把相同的内核与 DT 配置封装成 KRNL，再更新已核对边界的 eMMC kernel 区。
写前比对旧启动区摘要，写后同步并全量读回；还应比较整个启动前缀的预期变化，
确认 U-Boot、Trust、resource、boot 等保留区域没有意外改变。

### 5. 验证脱卡启动并收尾

正常关机，确认同步与文件系统卸载后，断开 12V、取出 TF，再接通电源。
用 DEBUG 串口确认原厂 U-Boot 加载内核、挂载 eMMC 根，再通过 SSH 检查服务。
分别验证一次断电上电和正常重启，不能用 RAM 试跑替代它们。

完成后清理一次性写入脚本、临时 HTTP 服务、挂载点和 kexec 任务，保留 TF 救援系统及校验记录。

## 容易遗漏的检查

- 准备阶段若用 udev 规则把 MMC 自动设为只读，不要把该规则复制进 eMMC 根系统。
- 临时输出放在实际存储上的目录；`/tmp` 可能是 tmpfs，不能用于大镜像暂存或存储性能验证。
- 为目标生成新的安全随机种子并启用 jitterentropy-rngd；永久 DTB 不嵌入固定种子。
- TF 救援系统使用 TF 设备树时默认看不到 eMMC；维护板载存储需要启用 eMMC 的受控 RAM 环境。
- eMMC 部署已替换 Android。恢复 Android 需要写回自己的备份，不能承诺取卡恢复或跨板克隆。

此方法的 RAM 根试启动、文件校验、eMMC 独立冷启动和正常重启已验证；
Android 镜像的刷回启动仍未验证。完整能力边界见 [支持矩阵](status.md)。
