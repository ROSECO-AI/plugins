"""Verify the bundled MCP process and its UTF-8 tool catalog without writing to Vitro."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    check_login = "--check-login" in sys.argv[1:]
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "vitro-installer-check", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    if check_login:
        messages.append({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                         "params": {"name": "vitro_whoami", "arguments": {}}})
    payload = ("\n".join(json.dumps(message) for message in messages) + "\n").encode("utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("mcp_server.py"))],
            input=payload, capture_output=True, timeout=90 if check_login else 20, check=True,
        )
        replies = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines()]
        by_id = {reply.get("id"): reply for reply in replies}
        if by_id[1]["result"]["serverInfo"]["name"] != "vitro-cad-local":
            raise ValueError("неверное имя сервера")
        names = {tool["name"] for tool in by_id[2]["result"]["tools"]}
        if not {"vitro_whoami", "vitro_list_projects", "vitro_delete_item"} <= names:
            raise ValueError("неполный список инструментов")
        if check_login:
            result = by_id[3]["result"]
            if result.get("isError"):
                raise RuntimeError(result["content"][0]["text"])
            identity = json.loads(result["content"][0]["text"])
            if not isinstance(identity, dict) or not isinstance(identity.get("user"), dict) or not (identity["user"].get("id") or identity["user"].get("name")):
                raise ValueError("Vitro-CAD не вернул пользователя")
    except RuntimeError as exc:
        print(f"Проверка MCP-сервера не пройдена: {exc}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"Проверка MCP-сервера не пройдена: {type(exc).__name__}.", file=sys.stderr)
        return 1
    print(f"MCP-сервер готов: {len(names)} инструментов" + ("; вход подтвержден." if check_login else "."))
    return 0


if __name__ == "__main__":
    # GitHub Windows runners and older terminals may select a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
