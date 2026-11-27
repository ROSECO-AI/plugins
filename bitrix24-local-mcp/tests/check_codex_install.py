"""Optional integration check against the installed CLI; no account or secret needed."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("CODEX_HOME") or not os.environ.get("TEST_CONFIG"):
    raise SystemExit("Use an isolated CODEX_HOME and synthetic TEST_CONFIG.")
Path(os.environ["CODEX_HOME"]).mkdir(parents=True, exist_ok=True)
codex = shutil.which("codex")
if not codex:
    raise SystemExit("Codex CLI is missing")


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise RuntimeError(f"Command failed: {args[0:3]}: {p.stderr}")
    return p.stdout


config = str(Path(os.environ["TEST_CONFIG"]).resolve())
run([sys.executable, str(ROOT / "runtime/install.py"), "--config", config, "--codex", codex])
# Idempotent registration must preserve the configured server.
run([sys.executable, str(ROOT / "runtime/install.py"), "--config", config, "--codex", codex])
entries = json.loads(run([codex, "mcp", "list", "--json"]))
entry = next(x for x in entries if x["name"] == "bitrix24-local")
assert entry["transport"]["command"] == sys.executable
assert entry["transport"]["args"][-2:] == ["--config", config]
run([codex, "plugin", "marketplace", "add", str(ROOT.parent)])
run([codex, "plugin", "add", "bitrix24-local-mcp@roseco-ai-plugins"])
listing = json.loads(run([codex, "plugin", "list", "--json"]))
plugin = next(p for p in listing["installed"] if p.get("name") == "bitrix24-local-mcp")
assert plugin["installed"] is True and plugin["enabled"] is True
assert plugin["version"] == "1.0.0"
print("Codex registration, repeat install and plugin discovery passed; no portal credentials used.")
