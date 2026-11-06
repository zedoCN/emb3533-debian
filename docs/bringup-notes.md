# 适配经验与故障定位

这些结论来自本次实机 bring-up，保留可复用的原因与判断方法。
地址和装载窗口只对已验证的板卡、固件及构建组合成立；当前支持范围以 [支持矩阵](status.md) 为准。

## 启动文件格式与整卡镜像

验证用旧 Rockchip 引导器分别读取 KRNL 封装的 kernel 和 ramdisk，不能用 Android-v0
单体 boot.img 直接代替。先用已知厂商文件校验封装工具，再逐区测试，比重复整卡覆盖更容易定位。
KRNL 工具的格式依据是固定厂商源码中的
[`scripts/mkkrnlimg.c`](https://github.com/rockchip-linux/kernel/blob/9ead5f3cbd6e0abd0ac70002205993c953c227ea/scripts/mkkrnlimg.c)。

第一版实验整卡镜像还遗漏了 SD 的 MBR。后来在实卡上分别修复 MBR、启动封装和 init 路径才启动成功。
因此，第一版压缩文件的摘要不能代表修复后的卡，也不能继续作为可启动镜像分发。
修改实卡之后，备份与清单需要对应实际最终状态，不能只保留最早一次写卡成功记录。

## ARM kexec 在 Bye! 后无输出

最初 kexec 后只见旧内核 `Bye!`。装载段都在 DRAM 内，仍不足以证明地址正确。
Debian 12 的 kexec-tools 2.0.25 按 `TEXT_OFFSET=0x8000` 估算，
而启用 ARCH_MESON 的 multi_v7 内核实际偏移为 `0x208000`，导致 initrd/DTB 与解压工作区冲突。

6.12.115 加上 `--mem-min=0x02000000 --mem-max=0x07ffffff` 后出现完整早期日志；
7.3.1 的无 initrd 试启动使用 `--mem-min=0x04000000 --mem-max=0x07ffffff`。
这是两次实际成功的窗口，不能直接推广到任意内核大小和内存布局。
本板还保留 `0x08400000–0x09200000` 的固件内存空洞，DTS 与装载器都不能覆盖它。

在诊断中，先后使用 earlycon、固定 UART 的 DEBUG_LL 与临时解压器日志。
解除 MULTIPLATFORM 下 DEBUG_UNCOMPRESS 限制的试验修改没有作为正式补丁发布。
正式配置与临时诊断配置应分开，避免把一次性调试入口留在默认启动中。

## timer：修改 DT 仍会崩溃

`rockchip_timer_init` 在设备树时钟初始化前直接访问 timer6/7 `0xff810000`，
验证用原厂固件下触发 external abort，因此仅禁用 DT 节点不够。
[`timer 补丁`](../patches/0001-emb3533-preserve-firmware-timer.patch) 对
`norco,emb3533` 跳过这段写入，保留固件已初始化的架构定时器。
板级 DT 使用原厂 timer0 `0xff6b0000` / IRQ66；实机日志确认 24MHz 架构定时器工作。

已确认的是该访问在此固件下异常；具体固件保护机制尚未独立证明，不能据此判断芯片损坏。

## DMA：节点名不等于 reg

下一次异常位于 `amba_read_periphid`。原厂 DMA 节点名虽然带 `ffb20000`，
其 `reg` 却使用非安全别名 `0xff600000`；主线默认启用的安全别名 `0xffb20000` 会异常。
禁用 `dmac_bus_s`、启用 `dmac_bus_ns` 后继续启动成功。

比较厂商与主线 DT 时，应看实际 `reg`、中断、供电和 phandle，不能只对照节点名。
原厂使用 secure-efuse 驱动；主线的直接 efuse 读取暂时禁用。
当前 CPU DVFS 关闭，网络身份由部署者配置，不依赖这里的 efuse 读取。

## 挂根与 init 的绝对软链接

早期 initramfs 用 `[ -x /newroot/sbin/init ]` 判断系统是否存在。
但该文件是指向 `/lib/systemd/systemd` 的绝对软链接，在切根前会解析到 initramfs 自己的 `/lib`，
造成误判；构建宿主恰好有同名文件时还可能假阳性。

修复为检查 `/newroot/lib/systemd/systemd`，移动 `/proc`、`/sys`、`/dev` 后，
执行 `switch_root /newroot /lib/systemd/systemd`。
读取 `/newroot/etc/debian_version` 只能证明根文件可读；切根后还需确认 PID 1 是 systemd。

7.3.1 路线使用内核直接挂载所选根分区，不再依赖这一 initramfs。
另一个相关问题是 `CONFIG_CMDLINE_EXTEND`：编译参数追加在 DT 参数之后，
其中固定的 `init=/init` 会破坏直接挂根，必须从编译参数中移除。

## 随机数不足会表现为网络迟迟不上线

首次单核 6.12 启动已进入 systemd，但 random-seed 等待、DHCP 未及时完成。
串口 SysRq 的任务栈说明系统仍响应，并非硬死机。
一次 RAM 试验通过每次新生成的 64 字节 `/chosen/rng-seed` 和
`random.trust_bootloader=on` 继续验证，消费后的种子 DTB 随即废弃。

永久方案安装并启用 `jitterentropy-rngd`，配合当前内核配置。
7.3.1 RAM 启动约 6.6 秒、断电上电约 10 秒完成 CRNG 初始化。
封装工具会移除 DT 中的种子，不能把同一固定种子提交 Git 或放进可重复使用的镜像。

## 确认测试真的覆盖了目标

- `findmnt` 的根来源可能显示 `/dev/root` 别名。用 `findmnt -rn -o MAJ:MIN /`
  对照目标分区的 sysfs `dev`，比仅比较路径可靠；`-r` 避免输出补空格。
- Debian 13 的 `/tmp` 可能是 tmpfs。TF 写入、fsync、回读和 SQLite 测试放在已确认落于 TF 的 `/var/tmp`。
- systemd 单元 active 不代表 HTTP 已监听；先确认监听，再从另一台机器访问。
- Mac 的代理环境可能把局域网请求送进代理。验证直连时使用 `curl --noproxy '*'`。
- 串口日志可能包含多次启动的 panic。按每次启动边界或偏移分段，结合 boot ID 判断当前运行结果。
- `panic=10` 可能自动退回默认内核；监测既要识别候选成功，也要识别已回退，避免无谓地要求再次断电。
- Debian 13 的 kexec-tools 2.0.29 已不带旧版 kexec-load 服务与 `LOAD_KEXEC` 变量；
  以实际软件包、unit 和 `kexec_loaded` 状态为准，不补回已经失效的配置。
