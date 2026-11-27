"""Synthetic-only tests: no Vitro-CAD account or live portal access."""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

SERVER = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER))
import credential_store  # noqa: E402
import mcp_server  # noqa: E402
import setup_windows  # noqa: E402
import vitro_api  # noqa: E402

GUID = "11111111-1111-4111-8111-111111111111"


class FakeClient:
    base_url = "https://portal.example.org"

    def __init__(self):
        self.calls = []

    def authenticate(self):
        return {"id": GUID, "name": "Synthetic user", "isAdmin": False}

    def call(self, path, **kwargs):
        self.calls.append(path)
        return [{"id": GUID}]


class ConnectorTests(unittest.TestCase):
    def test_portal_url_accepts_distinct_hosts_not_hardcoded_tenant(self):
        for url, expected in [("https://one.example.org/", "https://one.example.org"),
                              ("https://two.example.org:8443", "https://two.example.org:8443")]:
            self.assertEqual(vitro_api.validate_portal_url(url), expected)
        for bad in ["http://portal.example.org", "https://user:pass@portal.example.org",
                    "https://portal.example.org/api", "https://portal.example.org/?token=secret",
                    "https://portal.example.org/#fragment", " https://portal.example.org "]:
            with self.subTest(bad=bad), self.assertRaises(vitro_api.VitroError):
                vitro_api.validate_portal_url(bad)

    def test_api_redirect_is_rejected_and_never_forwards_token(self):
        self.assertIsNone(vitro_api._NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.example"))
        denied = HTTPError("https://portal.example.org/api/item/get/1", 302, "redirect",
                           {"Location": "https://elsewhere.example"}, None)
        with patch.object(vitro_api.request, "build_opener") as build:
            build.return_value.open.side_effect = denied
            with self.assertRaisesRegex(vitro_api.VitroError, "токен не передан"):
                vitro_api._request("https://portal.example.org", "api/item/get/1", token="SECRET")
            request_arg = build.return_value.open.call_args.args[0]
            self.assertEqual(request_arg.get_header("Authorization"), "SECRET")
            self.assertEqual(build.return_value.open.call_count, 1)

    def test_login_per_portal_and_2fa_stops(self):
        with patch.object(vitro_api, "_request", return_value={"status": 1, "token": "hidden", "user": {"id": GUID}}) as req:
            vitro_api.login("https://another.example.org", "user", "password")
            self.assertEqual(req.call_args.args[:2], ("https://another.example.org", "api/security/Login"))
        with patch.object(vitro_api, "_request", return_value={"status": 2, "user": {}}):
            with self.assertRaisesRegex(vitro_api.VitroError, "2FA"):
                vitro_api.login("https://another.example.org", "user", "password")

    def test_portal_and_account_stored_together_encrypted(self):
        with TemporaryDirectory() as td, patch.object(credential_store, "state_dir", return_value=Path(td)), \
             patch.object(credential_store, "_transform", side_effect=lambda data, *, encrypt: data):
            credential_store.save("https://one.example.org/", "user-a", "password-a", GUID)
            saved = credential_store.load()
            self.assertEqual((saved["portal"], saved["login"], saved["registry_list_id"]),
                             ("https://one.example.org", "user-a", GUID))
            credential_store.save("https://two.example.org", "user-b", "password-b")
            self.assertEqual(credential_store.load()["portal"], "https://two.example.org")
            credential_store.record_delete("https://one.example.org:" + GUID)
            self.assertFalse(credential_store.was_deleted("https://two.example.org:" + GUID))

    def test_whoami_has_portal_and_projects_need_explicit_registry(self):
        api = FakeClient()
        with patch.object(mcp_server, "active_client", return_value=api), \
             patch.object(mcp_server, "load", return_value={"registry_list_id": ""}):
            self.assertEqual(mcp_server.call_tool("vitro_whoami", {})["portal"], api.base_url)
            with self.assertRaisesRegex(ValueError, "GUID реестра"):
                mcp_server.call_tool("vitro_list_projects", {})
            result = mcp_server.call_tool("vitro_list_projects", {"registry_list_id": GUID})
            self.assertEqual(api.calls[-1], f"api/item/getList/{GUID}")
            self.assertEqual(result["items"][0]["id"], GUID)

    def test_mcp_protocol_discovery_and_no_read_network(self):
        response = mcp_server.respond({"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}})
        self.assertEqual(response["result"]["serverInfo"], {"name": "vitro-cad-local", "version": "1.0.0"})
        tools = mcp_server.respond({"id": 2, "method": "tools/list"})["result"]["tools"]
        self.assertEqual(len(tools), 12)
        self.assertIn("registry_list_id", next(x for x in tools if x["name"] == "vitro_list_projects")["inputSchema"]["properties"])
        self.assertIsNone(mcp_server.respond({"method": "notifications/initialized"}))

    def test_installer_mentions_three_agents_and_has_utf8_bom(self):
        root = SERVER.parent
        data = (root / "install_windows.ps1").read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        script = data.decode("utf-8-sig")
        for value in ("$portalBox", "$installCodex", "$installClaude", "$installQwen", "--credential-stdin"):
            self.assertIn(value, script)
        self.assertNotIn("roseco.vitrocad.ru", script.lower())


if __name__ == "__main__":
    unittest.main()
