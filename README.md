# self-hosted-vpn-speedup

自建 VPN 提速的 Codex Skill：保持 VPS 作为直连出口，通过实测排查限速、优化单连接接收窗口，并用多条独立隧道提高并发总吞吐。

An agent skill for measuring and improving a self-hosted VPS VPN, with Hysteria 2 / Mihomo tooling. MIT licensed. Version **0.1.1**.

## 能做什么

- 先查服务端、客户端、订阅生成器中的速率设置，区分限速与拥塞控制模式。
- 分别测单连接和并发总速度，重复对照后保留有效的接收窗口改进。
- 为同一 VPS 生成多个独立 Hysteria 2 节点，使用 round-robin 分配新连接。
- 测量不同隧道数量的收益和平台期，避免把“更多路”当成必然更快。
- 保存持久配置、校验、清理临时资源；尊重用户自行操作客户端按钮的要求。

单连接有效的窗口参数，也要在多路并发下单独复测；两种用途可以保留不同配置。

多路可以提高同时存在多个独立连接时的总速度。它不会自动把普通单连接下载拆成多份；分段下载器需要实际建立多个连接。所有速度统一报告为 **MB/s**。

## 使用 skill

将本仓库的 [`skills/self-hosted-vpn-speedup`](skills/self-hosted-vpn-speedup) 文件夹放入 Codex 的 skills 目录，或通过你的 skill 安装器从此仓库安装该路径。重新打开会话后调用：

```text
使用 $self-hosted-vpn-speedup 排查并提升我的自建 VPN 速度。
先测单连接，再测多隧道并发；保留实测有效的改动。
```

Windows 的常见安装目录是 `%USERPROFILE%\.codex\skills`；macOS/Linux 是 `~/.codex/skills`。如果设置了 `CODEX_HOME`，使用其中的 `skills` 目录。

## 独立使用工具

要求 Python 3.10+、已安装的 Mihomo 和 curl 7.75+。Python 工具没有第三方依赖，不会安装服务、切换节点、修改系统代理或自动重载客户端。

配置生成器读取本地私有 **JSON** 配置，保留认证与证书设置，输出新的私有文件。请将输入、输出保存在本仓库之外：

```sh
python skills/self-hosted-vpn-speedup/scripts/generate_mihomo_parallel.py --input /private/source.json --node "My VPS" --count 16 --selector "Proxy" --remove-rate-hints --large-windows --output /private/candidate.json
mihomo -t -f /private/candidate.json
```

`--remove-rate-hints` 和 `--large-windows` 可分别启用，方便单变量对照。生成器拒绝覆盖已有文件或撞名节点；流量是否经过新组取决于你自己的路由与选择。`/private/` 为示例路径，Windows 使用你自己的绝对路径。

测速工具对指定 HTTPS 对象建立独立 curl 连接，丢弃文件内容，核对下载字节数，用总字节数除以实际总耗时计算吞吐；请求未完成时返回失败，不把部分下载当成成功。完整命令及原理见 [操作参考](skills/self-hosted-vpn-speedup/references/hysteria2-mihomo.md)。

## 验证

```sh
python -m unittest discover -s tests -v
```

测试覆盖节点克隆、凭据与证书保留、拒绝链式节点、独立调优选项、私有文件不覆盖，以及测速对不完整响应的处理。技能中的版本基线为 Hysteria 2 2.12.3、Mihomo 1.19.32；其他版本须核对字段。

配置示例只有文档地址和虚构凭据。不要提交自己的节点、订阅、证书、密钥或测速中的私有数据。实际提升取决于线路、设备和业务；这套方法没有固定的最佳路数或速度保证。
