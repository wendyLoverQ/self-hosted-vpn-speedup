# Hysteria 2 + Mihomo: measured tuning

Compatibility baseline: Hysteria 2 **2.12.3**, Mihomo **1.19.32**, Python **3.10+**, curl **7.75+**. The helpers use only Python's standard library and invoke an already installed curl. They do not download or install VPN binaries. Check the installed core's version and schema before applying to another release. Mobile clients may expose different controls.

## Rate hints and controllers

Audit both ends and all generated aliases. Hysteria server `bandwidth.up` is toward the client; the reverse direction is server `bandwidth.down`. Mihomo proxy `up`/`down` are from the client's perspective. Server bandwidth limits currently govern Brutal mode, not BBR/Reno. Consult the [official bandwidth negotiation rules](https://v2.hysteria.network/docs/advanced/Full-Server-Config/#bandwidth).

To test adaptive control without old client rate hints, remove server `bandwidth` and client `up`/`down`, then set this server field if the installed version supports it:

```yaml
ignoreClientBandwidth: true
```

This overrides existing client rate hints and selects the configured non-Brutal controller (BBR by default). It is a controller change, not merely removing a limiter. Compare it with the baseline. Do not fill in arbitrarily huge rates to mean unlimited. BBR profiles are separate experiments; `aggressive` is not inherently fastest. Linux TCP BBR settings do not directly tune Hysteria's userspace QUIC controller.

## Receive windows

For a download, change the **client** receive windows. Test one node first. The [official performance guide](https://v2.hysteria.network/docs/advanced/Performance/#flow-control-receive-window-sizes) provides a larger-window example. Its Mihomo equivalents are:

```yaml
initial-stream-receive-window: 26843545
max-stream-receive-window: 26843545
initial-connection-receive-window: 67108864
max-connection-receive-window: 67108864
```

For the official Hysteria client the same values belong under `quic`, with keys `initStreamReceiveWindow`, `maxStreamReceiveWindow`, `initConnReceiveWindow`, `maxConnReceiveWindow`. The [pinned Mihomo adapter](https://github.com/MetaCubeX/mihomo/blob/v1.19.32/adapter/outbound/hysteria2.go) defines and forwards the four fields above.

These are flow-control byte windows, not fixed speed settings. Larger windows can help some high-delay paths and increase potential buffering, multiplied across active tunnels. Do not calculate a precise throughput ceiling from these values alone: congestion control, acknowledgements, packet loss and application consumption interact. Keep the settings only if A/B tests improve the relevant workload without resource pressure. A single-connection gain may disappear or reverse under many simultaneous tunnels. Compare both workloads; it is valid to keep a larger window only on the standalone node and default windows on parallel aliases.

## Independent tunnels

Create distinct node objects that all connect directly to the same VPS, then place their names in a round-robin load-balance group. [Mihomo documents the strategies here](https://wiki.metacubex.one/config/proxy-groups/load-balance/). Consistent hashing or sticky sessions can keep one destination on a single alias, defeating this experiment.

The generator consumes a **JSON configuration object**, accepted by Mihomo, rather than parsing YAML with ad hoc text substitutions. If the original is YAML, use a real YAML parser locally to prepare a private JSON copy; never paste secrets into a public converter. Run from the repository root, using private paths outside the checkout:

```sh
python skills/self-hosted-vpn-speedup/scripts/generate_mihomo_parallel.py --input /private/source.json --node "My VPS" --count 16 --selector "Proxy" --remove-rate-hints --large-windows --output /private/candidate.json
mihomo -t -f /private/candidate.json
```

For count-only experiments, omit the two tuning flags. Compare each candidate from the same original source. The generator intentionally rejects reusing its generated names and refuses to overwrite an existing output. Its 256-tunnel bound is a tool guard, not a network capacity claim. It creates private output permissions (0600 on POSIX; current user and SYSTEM on Windows). The output still contains the original credentials.

The group is available after generation, but traffic uses it only if the user's routing/selector sends traffic through it. The helper does not change runtime selection or add a universal MATCH rule. Verify egress IP, group/alias chains and server sockets while downloads run. If using an isolated test core, bind its proxy/controller to loopback, use unused ports and a fresh controller secret, disable TUN, and stop only that test process afterward.

## Throughput measurement

Choose an HTTPS object with a known body length and enough data for at least several seconds of transfer. For a range test, confirm the origin supports byte ranges and the exact requested size. Use separate curl processes so requests cannot collapse into one HTTP/2 connection. Example syntax (substitute your own object):

```sh
python skills/self-hosted-vpn-speedup/scripts/benchmark_proxy.py --proxy http://127.0.0.1:7890 --url https://downloads.example.net/test.bin --expected-bytes 25000000 --range --concurrency 1
python skills/self-hosted-vpn-speedup/scripts/benchmark_proxy.py --proxy http://127.0.0.1:7890 --url https://downloads.example.net/test.bin --expected-bytes 12500000 --range --concurrency 32
```

The example domain is a placeholder, not a provided speed-test service. By default, expected payload is limited to 1000 MB per invocation; change `--max-total-bytes` explicitly if needed. VPN, TLS and retransmission overhead consume additional traffic. Responses are discarded, never stored as downloads. The helper outputs JSON, exits nonzero for incomplete work, and does not claim success from partial bytes. It does not follow redirects; supply the final object URL.

Keep concurrency, source, per-request size and warm-up policy identical across tunnel-count candidates. Compare repeated single-connection runs separately from aggregate runs. If results plateau, examine CPU per core, memory, socket drops, RTT/loss, provider capacity and local connectivity. Test socket buffers or other system options individually, preserve unrelated workloads, and undo unsuccessful changes. Do not treat transport-declared loss as a direct measurement of physical packet loss.

## Persistence

Locate the application's actual enhancement pipeline before installing a transform. Some clients apply node extensions before script extensions; ordering and refresh behavior vary. Clone only after the base node exists. Avoid editing generated runtime files as the only persistent change. Preserve original TLS verification and test node count, alias inheritance and output schema after each refresh. Application latency checks may fail despite a working tunnel; validate with an actual request and exit IP.
