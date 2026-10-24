---
name: self-hosted-vpn-speedup
description: Diagnose and improve throughput of a self-hosted VPS VPN, especially Hysteria 2 with Mihomo/Clash, using measured receive-window tuning and independent parallel tunnels. Use for slow single connections or low aggregate VPN speed; parallel tunnels do not automatically split one download.
---

# Self-hosted VPN Speedup

Improve the user's existing direct VPS VPN and retain changes that show repeatable gains. Start with the actual client, server version, selected node, route and workload. Report speeds consistently in MB/s (bytes divided by 1,000,000); keep configuration values in the installed software's required syntax.

## Establish the bottleneck

Inspect running server configuration, persistent client source and generated runtime configuration. Check bandwidth fields, inherited rate hints, traffic shaping and provider quotas first. A configured rate is a ceiling or congestion-control input, not guaranteed throughput. Removing Hysteria bandwidth settings can also change its congestion controller.

Measure origin-to-VPS speed, one download through one tunnel, concurrent downloads through one tunnel, and the same concurrency through multiple tunnels. Use the same endpoint and byte count; repeat A/B/A/B tests and verify complete responses. A built-in tunnel speed test can separate tunnel behavior from origin behavior. Node latency is not throughput.

Use [scripts/benchmark_proxy.py](scripts/benchmark_proxy.py) for bounded, independent curl downloads through a local HTTP proxy. Aggregate speed is total completed bytes divided by wall time, not the sum of request rates. Partial or timed-out samples must not be reported as successful. Keep request concurrency fixed when comparing tunnel counts.

## Improve the relevant layer

Read [references/hysteria2-mihomo.md](references/hysteria2-mihomo.md) when working with Hysteria 2/Mihomo.

On a high-RTT path with adequate capacity, test larger QUIC receive windows on the receiving side. Verify installed-version support and change this separately from congestion control. Retain a repeatable gain without claiming it proves ISP per-connection policing.

For aggregate throughput, clone the same direct Hysteria node under distinct names and use a `load-balance` group with `round-robin`. Preserve authentication, server, SNI and certificate verification. Confirm independent outer tunnel connections actually open in the installed core; aliases alone are not proof.

Use [scripts/generate_mihomo_parallel.py](scripts/generate_mihomo_parallel.py) to make a private candidate from a local JSON config. It preserves unrelated settings and credentials, rejects chained bases and name collisions, and never reloads the application. Rate-hint removal and larger windows are separate explicit options.

Increase counts such as 2, 4, 8 and 16 only while measurements improve. Stop at a plateau, regression, resource pressure or the user's traffic budget. There is no universal optimal count. HTTP/2 streams within one TCP connection remain on one tunnel. A segmented downloader needs independent connections; this technique does not stripe arbitrary single-flow packets.

## Apply and report

Preserve the chosen direct exit and the user's application-control preferences. Use isolated listeners for trials when an active-proxy change would interrupt work. If the user wants to press activation buttons, save and validate the persistent source and leave activation to them. Update subscription generators too, so refreshes preserve the change.

Keep private configs outside this public skill. Do not print or publish credentials, subscription URLs, controller secrets or private environment details. Respect the user's backup preference. Remove temporary services, firewall rules and credential files; restore temporary system settings. Do not alter unrelated VPS services.

Report verified before/after MB/s, workload, single versus aggregate results, saved/applied state and remaining device validation. A desktop result does not validate a phone. Monthly traffic allowances are not unlimited capacity.
