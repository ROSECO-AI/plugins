from __future__ import annotations

import json
import platform
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from vitro_license_monitor.api import ApiError, _safe_error
from vitro_license_monitor.collector import LicenseReading, collect, discover_active_license_field
from vitro_license_monitor.config import Settings, load_settings, save_settings
from vitro_license_monitor.credentials import CredentialError, load_token, save_token
from vitro_license_monitor.dashboard import build_model, render
from vitro_license_monitor.storage import Storage


def lookup(name: str) -> dict:
    return {"fieldValueMap": {"name": name}}


def settings() -> Settings:
    return Settings(
        base_url="https://vitro.example.test",
        login="monitor@example.test",
        user_list_id="users-list",
        active_license_field="principal_active_license_type",
        web_capacity=20,
        pro_capacity=50,
    )


class MonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def users(self) -> list[dict]:
        return [
            {"fieldValueMap": {"content_type_id": lookup("Пользователь"), "principal_active_license_type": lookup("WEB"), "email": "hidden@example.test"}},
            {"fieldValueMap": {"content_type_id": lookup("Пользователь"), "principal_active_license_type": lookup("PRO"), "name": "Hidden Person"}},
            {"fieldValueMap": {"content_type_id": lookup("Пользователь"), "principal_active_license_type": None}},
        ]

    def test_discovers_known_active_license_field(self) -> None:
        self.assertEqual(discover_active_license_field(self.users()), "principal_active_license_type")

    def test_collect_returns_aggregates_only(self) -> None:
        with patch("vitro_license_monitor.collector.request_json", return_value=self.users()):
            reading, field = collect(settings(), "secret-token")
        self.assertEqual((reading.web_active, reading.pro_active, reading.without_active_license), (1, 1, 1))
        self.assertEqual(reading.total_users, 3)
        self.assertEqual(field, "principal_active_license_type")
        self.assertNotIn("hidden", repr(reading).casefold())

    def test_unknown_license_value_is_rejected(self) -> None:
        users = self.users()
        users[0]["fieldValueMap"]["principal_active_license_type"] = lookup("OTHER")
        with patch("vitro_license_monitor.collector.request_json", return_value=users):
            with self.assertRaises(ApiError):
                collect(settings(), "secret-token")

    def test_unvalidated_user_list_is_rejected(self) -> None:
        items = [
            {"fieldValueMap": {"principal_active_license_type": lookup("WEB")}},
            {"fieldValueMap": {"principal_active_license_type": lookup("PRO")}},
        ]
        with patch("vitro_license_monitor.collector.request_json", return_value=items):
            with self.assertRaises(ApiError):
                collect(settings(), "secret-token")

    def test_storage_schema_has_no_personal_fields(self) -> None:
        storage = Storage(self.root / "monitor.sqlite3")
        storage.add(LicenseReading(datetime.now(timezone.utc), 2, 3, 4, 9, 50))
        columns = storage.columns()
        self.assertNotIn("email", columns)
        self.assertNotIn("name", columns)
        self.assertNotIn("user_id", columns)

    def test_dashboard_contains_all_periods_and_buttons(self) -> None:
        storage = Storage(self.root / "monitor.sqlite3")
        storage.add(LicenseReading(datetime.now(timezone.utc), 2, 3, 4, 9, 50))
        model = build_model(settings(), storage)
        page = render(settings(), model)
        self.assertEqual(set(model["histories"]), {"day", "week", "month"})
        self.assertIn('data-range="day"', page)
        self.assertIn('data-range="week"', page)
        self.assertIn('data-range="month"', page)
        self.assertNotIn("cdn.", page.casefold())

    def test_config_rejects_secret_fields(self) -> None:
        path = self.root / "config.json"
        path.write_text(json.dumps({"base_url": "https://x.test", "login": "x", "token": "secret"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_settings(path)

    def test_saved_config_contains_no_token_or_password(self) -> None:
        path = self.root / "config.json"
        save_settings(settings(), path)
        text = path.read_text(encoding="utf-8").casefold()
        self.assertNotIn('"token"', text)
        self.assertNotIn('"password"', text)

    def test_http_errors_are_redacted(self) -> None:
        raw = json.dumps({"token": "secret", "exception": {"message": "denied", "securitySession": {"email": "hidden@example.test"}}})
        safe = _safe_error(raw)
        self.assertNotIn("secret", safe)
        self.assertNotIn("hidden@example.test", safe)
        self.assertNotIn("denied", safe)

    def test_macos_keychain_adapter_does_not_return_command_output_on_failure(self) -> None:
        ok = type("Result", (), {"returncode": 0, "stdout": "saved-token\n"})()
        with patch.object(platform, "system", return_value="Darwin"), patch(
            "vitro_license_monitor.credentials.subprocess.run", return_value=ok
        ) as run:
            self.assertEqual(load_token("https://vitro.example.test", "user@example.test"), "saved-token")
            save_token("https://vitro.example.test", "user@example.test", "new-token")
        self.assertEqual(run.call_count, 2)

    def test_windows_dpapi_adapter_roundtrip_contract(self) -> None:
        token_path = self.root / "token.dat"

        def fake_powershell(script: str, value: str) -> str:
            return "encrypted" if "Protect(" in script and "Unprotect(" not in script else "plain-token"

        with patch.object(platform, "system", return_value="Windows"), patch(
            "vitro_license_monitor.credentials._windows_path", return_value=token_path
        ), patch("vitro_license_monitor.credentials._powershell", side_effect=fake_powershell):
            save_token("https://vitro.example.test", "user@example.test", "plain-token")
            self.assertEqual(token_path.read_text(encoding="ascii"), "encrypted")
            self.assertEqual(load_token("https://vitro.example.test", "user@example.test"), "plain-token")

    def test_unsupported_operating_system_is_explicit(self) -> None:
        with patch.object(platform, "system", return_value="Linux"):
            with self.assertRaises(CredentialError):
                load_token("https://vitro.example.test", "user@example.test")


if __name__ == "__main__":
    unittest.main()
