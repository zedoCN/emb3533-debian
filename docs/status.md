# 适配状态

## 已确认

6.12.115 的 RAM 试启动使用 `--mem-min=0x02000000 --mem-max=0x07ffffff`。
旧 kexec-tools 按 0x8000 估算 ARM TEXT_OFFSET，但 multi_v7 的实际值可能为 0x208000，导致解压区与 initrd/DTB 重叠。

原厂固件下直接访问 timer6/7 (0xff810000) 会 external abort。板级补丁跳过该初始化，保留已运行的架构计时器，DT 使用 timer0。
DMA 使用非安全别名 0xff600000；禁用安全别名 0xffb20000。测试不使用 secure efuse。

首次单核试启动遇到熵不足；后续由装载器传入每次新生成的随机种子后启动成功。
固定种子不能作为长期启动方案；独立启动必须另行验证随机数初始化。

## 7.3.1 与 Debian 13

7.3.1 已完成 RAM 试启动：不带 initrd，直接挂载 TF ext4 根分区；四核从启动起在线。
安装 `jitterentropy-rngd` 后，随机数约 6 秒完成初始化，无需固定或人工注入种子。

持久启动使用 `CONFIG_ARM_APPENDED_DTB=y`，关闭 `CONFIG_ARM_ATAG_DTB_COMPAT`。
`make_kernel_image.py` 将明确的根设备和 `/lib/systemd/systemd` 写入 DT bootargs，追加 DTB，再封装 KRNL。
原厂 U-Boot 仍读取原 resource 完成硬件初始化；Linux 使用追加的主线 DTB。
MMC、供电和 ext4 驱动内置，因此无需 initramfs 即可挂根。

已经从原厂 U-Boot 正常重启进入 7.3.1，随后升级到 Debian 13.7。
完整内核模块已安装，模块 vermagic 与运行内核一致，加载测试通过。
升级后实际断电上电通过。CRNG约10秒初始化，SSH自动恢复，四核在线，无失败服务。
四个Python进程分别固定在CPU0/1/2/3计算通过；TF上的文件写入/fsync/回读和SQLite通过；
DNS与系统安全随机数正常，Mac直连临时HTTP服务返回200。测试服务随后已停止。

## 当前边界

- HDMI/DRM、媒体、声音、CPU 调频/idle 关闭。这是通过 SSH 使用的命令行配置。
- USB、Wi-Fi、温控与长期满载稳定性未验收，不能把已有模块等同于板级接口可用。
- eMMC 在实验设备树中禁用，当前启动只面向 TF。
- 软件关机已卸载文件系统，但目前不会切断板卡电源，随后出现RCU停机警告；需要手动断12V。
  这不属于已完成的PMIC关机支持，正常运行与冷启动后未见该警告。
- 本仓库不提供通用整卡刷写脚本，也不包含原厂启动固件或个人系统镜像。
- 在刷写前备份自己的卡；回退时应使用匹配的系统和启动区备份，不能假定 Debian 13 可以直接退回厂商 4.4 内核。
