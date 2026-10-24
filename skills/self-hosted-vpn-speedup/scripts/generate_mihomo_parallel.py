#!/usr/bin/env python3
"""Generate a private Mihomo candidate; never apply it or print its secrets."""

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess

WINDOWS = {
    "initial-stream-receive-window": 26843545,
    "max-stream-receive-window": 26843545,
    "initial-connection-receive-window": 67108864,
    "max-connection-receive-window": 67108864,
}


def build_config(source, node_name, count, group_name=None, selector=None,
                 remove_rate_hints=False, large_windows=False):
    if not isinstance(source, dict):
        raise ValueError("Input must be a Mihomo JSON configuration object")
    if not 1 <= count <= 256:
        raise ValueError("Generator supports 1..256 tunnels; this is not a network limit")
    config = copy.deepcopy(source)
    proxies = config.get("proxies", [])
    groups = config.get("proxy-groups", [])
    if not isinstance(proxies, list) or not isinstance(groups, list):
        raise ValueError("proxies and proxy-groups must be lists")
    entries = proxies + groups
    if any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
           for item in entries):
        raise ValueError("Every proxy/group must have a name")
    names = [item["name"] for item in entries]
    if len(names) != len(set(names)):
        raise ValueError("Input contains duplicate proxy/group names")
    base = next((item for item in proxies if item["name"] == node_name), None)
    if base is None or base.get("type") != "hysteria2":
        raise ValueError("Selected base must be a Hysteria 2 proxy")
    if base.get("dialer-proxy"):
        raise ValueError("Selected base is chained; choose a direct VPS proxy")
    if not base.get("server") or not base.get("port"):
        raise ValueError("Selected base needs server and port")
    group_name = group_name or f"{node_name} {count} tunnels"
    aliases = [f"{node_name} [tunnel {i:02d}]" for i in range(1, count + 1)]
    generated = [group_name] + aliases
    if len(generated) != len(set(generated)) or set(generated).intersection(names):
        raise ValueError("Generated names collide; use a fresh source or different group")
    parent = None
    if selector:
        parent = next((item for item in groups if item["name"] == selector), None)
        if parent is None or parent.get("type") != "select" or not isinstance(parent.get("proxies"), list):
            raise ValueError("Parent selector must be an existing select group with a proxies list")
    if remove_rate_hints:
        base.pop("up", None)
        base.pop("down", None)
    if large_windows:
        base.update(WINDOWS)
    for alias in aliases:
        node = copy.deepcopy(base)
        node["name"] = alias
        proxies.append(node)
    groups.append({"name": group_name, "type": "load-balance", "strategy": "round-robin",
                   "proxies": aliases, "url": "https://www.gstatic.com/generate_204",
                   "interval": 300, "lazy": True})
    if parent is not None:
        parent["proxies"].insert(0, group_name)
    config["proxies"] = proxies
    config["proxy-groups"] = groups
    return config


def write_private_json(path, config):
    """Create a new file, restrict its permissions before writing private data."""
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "nt":
            domain = os.environ.get("USERDOMAIN", "")
            user = os.environ["USERNAME"]
            principal = f"{domain}\\{user}" if domain else user
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                            principal + ":F", "SYSTEM:F"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except BaseException:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Private JSON config, not YAML")
    parser.add_argument("--node", required=True, help="Existing direct Hysteria 2 proxy name")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--group")
    parser.add_argument("--selector", help="Existing select group to add the generated group to")
    parser.add_argument("--remove-rate-hints", action="store_true")
    parser.add_argument("--large-windows", action="store_true")
    parser.add_argument("--output", required=True, type=Path, help="NEW private JSON file outside the public repo")
    args = parser.parse_args()
    try:
        source = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = build_config(source, args.node, args.count, args.group, args.selector,
                              args.remove_rate_hints, args.large_windows)
        write_private_json(args.output, result)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if isinstance(error, FileExistsError):
            reason = "Output exists; no file was changed"
        elif type(error) is ValueError:
            reason = str(error)
        else:
            reason = f"Private config operation failed ({type(error).__name__})"
        parser.exit(2, reason + "\n")
    print(json.dumps({"candidate_created": True, "tunnels": args.count,
                      "rate_hints_removed": args.remove_rate_hints,
                      "large_windows": args.large_windows, "application_reloaded": False}))


if __name__ == "__main__":
    main()
