#!/usr/bin/env python3
"""Bounded independent curl downloads; no VPN selection or configuration changes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import time
from urllib.parse import urlsplit


def summarize(rows, elapsed):
    valid = bool(rows) and elapsed > 0 and all(row["complete"] for row in rows)
    size = sum(row["downloaded_bytes"] for row in rows)
    return {"valid": valid, "requests": len(rows), "downloaded_bytes": size,
            "elapsed_seconds": round(elapsed, 6),
            "aggregate_MB_s": round(size / elapsed / 1_000_000, 4) if valid else None,
            "samples": rows}


def download(url, proxy, expected_bytes, timeout, use_range, curl="curl"):
    command = [curl, "--proxy", proxy, "--noproxy", "", "--silent", "--show-error",
               "--connect-timeout", str(min(10, timeout)), "--max-time", str(timeout),
               "--max-filesize", str(expected_bytes), "--output", os.devnull,
               "--write-out", "%{json}"]
    if use_range:
        command += ["--range", f"0-{expected_bytes - 1}"]
    command += ["--", url]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout + 5, creationflags=flags)
        raw = json.loads(proc.stdout)
        size = int(raw.get("size_download", 0))
        code = int(raw.get("http_code", 0))
        complete = proc.returncode == 0 and code in (200, 206) and size == expected_bytes
        return {"complete": complete, "downloaded_bytes": size, "http_code": code,
                "curl_exit_code": proc.returncode, "request_seconds": raw.get("time_total")}
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as error:
        return {"complete": False, "downloaded_bytes": 0, "error": type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy", required=True, help="Local HTTP proxy, e.g. http://127.0.0.1:7890")
    parser.add_argument("--url", required=True, help="HTTPS test object that you are authorized to download")
    parser.add_argument("--expected-bytes", required=True, type=int, help="Exact response body size per request")
    parser.add_argument("--range", action="store_true", dest="use_range", help="Request bytes 0..expected-1")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--requests", type=int, help="Default: same as concurrency")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-total-bytes", type=int, default=1_000_000_000,
                        help="Expected payload budget, default 1000 MB; excludes protocol overhead")
    parser.add_argument("--curl", default="curl")
    args = parser.parse_args()
    proxy = urlsplit(args.proxy)
    target = urlsplit(args.url)
    if (proxy.scheme != "http" or proxy.hostname not in ("127.0.0.1", "localhost", "::1")
            or not proxy.port or proxy.username or proxy.password):
        parser.error("Use a loopback HTTP proxy without credentials in the URL")
    if target.scheme != "https" or not target.hostname or target.username or target.password:
        parser.error("Use an HTTPS test URL without credentials in the URL")
    count = args.requests if args.requests is not None else args.concurrency
    if not (1 <= args.concurrency <= 256 and 1 <= count <= 4096 and 1 <= args.timeout <= 300):
        parser.error("Use concurrency 1..256, requests 1..4096, timeout 1..300 seconds")
    if args.expected_bytes <= 0 or args.expected_bytes * count > args.max_total_bytes:
        parser.error("Expected download size exceeds the payload budget or is invalid")
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        tasks = [pool.submit(download, args.url, args.proxy, args.expected_bytes,
                             args.timeout, args.use_range, args.curl) for _ in range(count)]
        rows = [task.result() for task in tasks]
    report = summarize(rows, time.perf_counter() - started)
    report["concurrency"] = args.concurrency
    print(json.dumps(report))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
