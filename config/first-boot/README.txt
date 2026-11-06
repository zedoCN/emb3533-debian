EMB-3533 Debian: first boot / 首次启动

1. Copy your SSH PUBLIC key to this volume as authorized_keys (no .txt suffix).
   把 SSH 公钥复制到本分区，命名为 authorized_keys。不要放私钥。
2. Optional: copy setup.json.example to setup.json and edit hostname / Wi-Fi.
   可选：复制示例为 setup.json，修改主机名和 2.4GHz WPA2 Wi-Fi。
   With Ethernet only, omit setup.json. 不配 Wi-Fi 可省略 setup.json。
3. Eject the card, insert it into the board, connect Ethernet (unless Wi-Fi is
   configured), and power on. 首次启动自动扩容；用 debian 用户和公钥 SSH 登录。

There is no default password or root login. No key means no SSH login; shut down,
add authorized_keys here and boot again. 没放公钥时不会开放默认密码。
Only declarative JSON is accepted; files here are never executed as scripts.
Successful import removes authorized_keys and setup.json. The card remains
private: deleting a file does not securely erase flash. 配置文件删除不等于安全擦除。
Import runs only until the first successful setup, not on every reboot.

This image is for the supported NORCO EMB-3533 hardware/firmware revision only.
See https://github.com/zedoCN/emb3533-debian for support limits and recovery.
