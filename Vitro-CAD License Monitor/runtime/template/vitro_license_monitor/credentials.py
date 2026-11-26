from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


SERVICE_PREFIX = "vitro-cad-license-monitor"


class CredentialError(RuntimeError):
    pass


def _identity(base_url: str, login: str) -> tuple[str, str]:
    host = urlparse(base_url).hostname or "vitro"
    digest = hashlib.sha256(f"{base_url}|{login}".encode()).hexdigest()[:16]
    return f"{SERVICE_PREFIX}:{host}:{digest}", login


def _windows_path(base_url: str, login: str) -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    service, _ = _identity(base_url, login)
    digest = hashlib.sha256(service.encode()).hexdigest()[:20]
    return root / "ROSECO" / "VitroCADLicenseMonitor" / f"{digest}.token"


def _powershell(script: str, input_text: str) -> str:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if not executable:
        raise CredentialError("Windows PowerShell is required for DPAPI token storage")
    result = subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CredentialError("Windows DPAPI operation failed")
    return result.stdout.strip()


def save_token(base_url: str, login: str, token: str) -> None:
    system = platform.system()
    service, account = _identity(base_url, login)
    if system == "Darwin":
        result = subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-s",
                service,
                "-a",
                account,
                "-w",
                token,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise CredentialError("Could not save token to macOS Keychain")
        return
    if system == "Windows":
        script = (
            "$p=[Console]::In.ReadToEnd();"
            "$b=[Text.Encoding]::UTF8.GetBytes($p);"
            "$e=[Security.Cryptography.ProtectedData]::Protect($b,$null,"
            "[Security.Cryptography.DataProtectionScope]::CurrentUser);"
            "[Convert]::ToBase64String($e)"
        )
        encrypted = _powershell(script, token)
        path = _windows_path(base_url, login)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encrypted, encoding="ascii")
        return
    raise CredentialError("Version 1.0.0 supports secure token storage only on macOS and Windows")


def load_token(base_url: str, login: str) -> str | None:
    system = platform.system()
    service, account = _identity(base_url, login)
    if system == "Darwin":
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None
    if system == "Windows":
        path = _windows_path(base_url, login)
        if not path.exists():
            return None
        script = (
            "$p=[Console]::In.ReadToEnd();"
            "$e=[Convert]::FromBase64String($p);"
            "$b=[Security.Cryptography.ProtectedData]::Unprotect($e,$null,"
            "[Security.Cryptography.DataProtectionScope]::CurrentUser);"
            "[Text.Encoding]::UTF8.GetString($b)"
        )
        return _powershell(script, path.read_text(encoding="ascii")).strip() or None
    raise CredentialError("Version 1.0.0 supports secure token storage only on macOS and Windows")
