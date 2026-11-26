from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CONFIG_PATH = Path("config.json")


@dataclass(frozen=True)
class Settings:
    base_url: str
    login: str
    user_list_id: str = ""
    active_license_field: str = ""
    content_type_field: str = "content_type_id"
    user_content_type_name: str = "Пользователь"
    web_capacity: int = 20
    pro_capacity: int = 20
    warning_ratio: float = 0.8
    timezone: str = "Europe/Moscow"
    stale_after_minutes: int = 120
    database_path: str = "data/license_monitor.sqlite3"
    dashboard_path: str = "output/license-dashboard.html"
    token_expires_at: str = ""

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTPS URL")
        if not self.login.strip():
            raise ValueError("login is required")
        if self.web_capacity < 1 or self.pro_capacity < 1:
            raise ValueError("WEB and PRO capacities must be positive")
        if not 0 < self.warning_ratio <= 1:
            raise ValueError("warning_ratio must be in (0, 1]")

    def resolve_path(self, value: str, config_path: Path = CONFIG_PATH) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (config_path.resolve().parent / path)


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    if not path.exists():
        raise FileNotFoundError(f"Configuration not found: {path}. Run configure first.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config.json must contain an object")
    forbidden = {"password", "token", "authorization", "cookie"}
    leaked = forbidden.intersection(key.casefold() for key in raw)
    if leaked:
        raise ValueError("Secrets are forbidden in config.json")
    settings = Settings(**raw)
    settings.validate()
    return settings


def save_settings(settings: Settings, path: Path = CONFIG_PATH) -> None:
    settings.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def updated(settings: Settings, **changes: Any) -> Settings:
    values = asdict(settings)
    values.update(changes)
    result = Settings(**values)
    result.validate()
    return result
