from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from .api import ApiError, list_id_from_login, login
from .collector import collect
from .config import CONFIG_PATH, Settings, load_settings, save_settings, updated
from .credentials import CredentialError, load_token, save_token
from .dashboard import build_model, render
from .storage import Storage


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _configure(path: Path) -> int:
    current = load_settings(path) if path.exists() else None
    settings = Settings(
        base_url=_prompt("Vitro-CAD HTTPS URL", current.base_url if current else "https://vitro.example.ru"),
        login=_prompt("Vitro-CAD login", current.login if current else ""),
        user_list_id=current.user_list_id if current else "",
        active_license_field=current.active_license_field if current else "",
        content_type_field=current.content_type_field if current else "content_type_id",
        user_content_type_name=current.user_content_type_name if current else "Пользователь",
        web_capacity=_positive(_prompt("Purchased WEB licenses", str(current.web_capacity if current else 20))),
        pro_capacity=_positive(_prompt("Purchased PRO licenses", str(current.pro_capacity if current else 20))),
        warning_ratio=current.warning_ratio if current else 0.8,
        timezone=_prompt("Timezone", current.timezone if current else "Europe/Moscow"),
        stale_after_minutes=current.stale_after_minutes if current else 120,
        database_path=current.database_path if current else "data/license_monitor.sqlite3",
        dashboard_path=current.dashboard_path if current else "output/license-dashboard.html",
        token_expires_at=current.token_expires_at if current else "",
    )
    save_settings(settings, path)
    print(path.resolve())
    print("No password or token was saved to config.json.")
    return 0


def _login(path: Path) -> int:
    settings = load_settings(path)
    password = getpass.getpass("Vitro-CAD password (input is hidden): ")
    if not password:
        raise ApiError("Password is required")
    response = login(settings.base_url, settings.login, password)
    password = ""
    list_id = list_id_from_login(response) or settings.user_list_id
    if not list_id:
        raise ApiError("Login succeeded, but the user list ID could not be discovered")
    token = str(response["token"])
    save_token(settings.base_url, settings.login, token)
    token = ""
    settings = updated(
        settings,
        user_list_id=list_id,
        token_expires_at=str(response.get("expires") or ""),
    )
    save_settings(settings, path)
    print("Vitro-CAD authentication succeeded.")
    print("The token was saved in the operating-system credential store.")
    if settings.token_expires_at:
        print(f"Session expires: {settings.token_expires_at}")
    return 0


def _storage(settings: Settings, path: Path) -> Storage:
    return Storage(settings.resolve_path(settings.database_path, path))


def _collect(path: Path) -> int:
    settings = load_settings(path)
    token = load_token(settings.base_url, settings.login)
    if not token:
        raise ApiError("No saved Vitro-CAD token. Run: python -m vitro_license_monitor.cli login")
    reading, field = collect(settings, token)
    token = ""
    if field != settings.active_license_field:
        settings = updated(settings, active_license_field=field)
        save_settings(settings, path)
    row = _storage(settings, path).add(reading)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def _status(path: Path) -> int:
    settings = load_settings(path)
    latest = _storage(settings, path).latest()
    print(json.dumps({"latest": latest}, ensure_ascii=False, indent=2))
    return 0 if latest else 1


def _dashboard(path: Path) -> int:
    settings = load_settings(path)
    storage = _storage(settings, path)
    target = settings.resolve_path(settings.dashboard_path, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(settings, build_model(settings, storage)), encoding="utf-8")
    print(target.resolve())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Vitro-CAD license monitor")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("command", choices=("configure", "login", "collect", "status", "dashboard"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "configure":
            return _configure(args.config)
        if args.command == "login":
            return _login(args.config)
        if args.command == "collect":
            return _collect(args.config)
        if args.command == "status":
            return _status(args.config)
        if args.command == "dashboard":
            return _dashboard(args.config)
    except (ApiError, CredentialError, FileNotFoundError, ValueError) as exc:
        message = str(exc)
        print(f"ERROR: {message}", file=sys.stderr)
        if isinstance(exc, ApiError) and exc.status == 401:
            print("Refresh the token with: python -m vitro_license_monitor.cli login", file=sys.stderr)
        elif isinstance(exc, ApiError) and exc.status == 403:
            print("The account lacks permission to read the required Vitro-CAD list.", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
