#!/usr/bin/env python3
"""Install the bundled server using this interpreter's absolute path. No secrets.

This installer never copies a webhook, changes portal settings or overwrites
an unrelated MCP registration. Python 3.10+; Windows/macOS/Linux.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from bitrix24_mcp_server import VERSION, default_config_path


def run_codex(executable, args):
    # Windows npm installs may expose codex.cmd. Arguments are installer-generated
    # paths/names, never credentials. subprocess handles list quoting.
    return subprocess.run([executable, *args], capture_output=True, text=True, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--server-name", default="bitrix24-local")
    parser.add_argument("--codex", help="Absolute Codex CLI path if not on PATH")
    parser.add_argument("--prepare-only", action="store_true", help="Deploy files without registering MCP")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python 3.10+ is required")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.server_name):
        parser.error("Server name must contain only letters, digits, hyphens, underscores")
    config = (args.config or default_config_path()).expanduser().resolve()
    target = config.parent / "runtime" / "bitrix24_mcp_server.py"
    source = Path(__file__).with_name("bitrix24_mcp_server.py")
    codex = args.codex or shutil.which("codex")
    if not args.prepare_only:
        if not codex:
            parser.error("Codex CLI not found. Use --codex <absolute-path> or --prepare-only.")
        # Inspect inventory instead of interpreting any failed 'get' as absence.
        listed = run_codex(codex, ["mcp", "list", "--json"])
        try:
            if listed.returncode:
                raise ValueError
            entries = json.loads(listed.stdout)
            if not isinstance(entries, list):
                raise ValueError
        except ValueError:
            parser.error("Cannot inspect Codex MCP inventory; nothing changed. Check CLI access.")
        existing = next((x for x in entries if x.get("name") == args.server_name), None)
        if existing:
            transport = existing.get("transport", {})
            expected_args = ["-u", str(target), "--config", str(config)]
            if transport.get("command") != sys.executable or transport.get("args") != expected_args:
                parser.error("An MCP with this name already exists. Nothing changed. Use --server-name bitrix24-local-new and compare before migrating.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        parser.error("Refusing to replace a symlink")
    content = source.read_bytes()
    fd, temp = tempfile.mkstemp(prefix=".server-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    if not args.prepare_only:
        added = run_codex(codex, ["mcp", "add", args.server_name, "--", sys.executable,
                                  "-u", str(target), "--config", str(config)])
        if added.returncode:
            print("Server deployed, but MCP registration failed. Credentials were not changed.", file=sys.stderr)
            return 1
    print(json.dumps({"version": VERSION, "server": str(target), "config": str(config),
                      "python": sys.executable, "registered": not args.prepare_only,
                      "sha256": hashlib.sha256(content).hexdigest()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
