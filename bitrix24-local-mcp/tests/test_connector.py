from __future__ import annotations
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
import bitrix24_mcp_server as m
import install

HOOK = "https://portal.example.org/rest/1/synthetic_secret_123456/"


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.json"
        # Keep SYSTEMROOT, USERPROFILE and TLS-related variables on Windows.
        self.env = patch.dict(os.environ, {"BITRIX24_WEBHOOK_URL": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        m.save_config(self.path, {"portal": "https://portal.example.org", "webhook_url": HOOK, "writes_enabled": False})
        self.client = m.Client(self.path)

    def response(self, data):
        response = Mock()
        response.read.return_value = json.dumps(data).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        self.client.opener.open = Mock(return_value=response)
        return response

    def test_custom_portals_and_subdirectory(self):
        for url in [HOOK, "https://custom.example.org:8443/product/rest/23/synthetic_secret/"]:
            self.assertEqual(m.validate_webhook(url), url)

    def test_bad_webhook_urls_rejected(self):
        for url in [HOOK.replace("https:", "http:"), HOOK + "?x=y", HOOK + "#frag",
                    HOOK.replace("portal", "user:password@portal"), HOOK + "tasks.task.list.json",
                    "https://portal.example.org/../rest/1/secret/", "https://[broken/rest/1/secret/",
                    "https://portal.example.org:bad/rest/1/secret/", HOOK + " ", HOOK.replace("rest", "%72est")]:
            with self.subTest(url=url), self.assertRaises(m.ConnectorError):
                m.validate_webhook(url)

    def test_reject_wrong_portal_even_env_override(self):
        with patch.dict(os.environ, {"BITRIX24_WEBHOOK_URL": HOOK.replace("portal.", "different.")}):
            client = m.Client(self.path)
        with self.assertRaisesRegex(m.ConnectorError, "differs"):
            client.call("profile")

    def test_read_preserves_pagination(self):
        body = {"result": [{"ID": "1"}], "next": 50, "total": 71, "time": {"duration": 0.1}}
        self.response(body)
        self.assertEqual(self.client.call("crm.deal.list", {"start": 0}), body)

    def test_find_tasks_continuation(self):
        self.response({"result": {"tasks": []}, "next": 100})
        result = m.call_tool(self.client, "bitrix24_find_tasks", {"start": 50, "select": ["ID"]})
        self.assertFalse(result["isError"])
        request = self.client.opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data)["start"], 50)
        self.assertEqual(json.loads(result["content"][0]["text"])["next"], 100)

    def test_non_read_cannot_bypass_read_gate(self):
        self.response({"result": True})
        for method in ["tasks.task.add", "tasks.task.delete", "evil.get", "evil.list", "batch"]:
            with self.subTest(method=method), self.assertRaises(m.ConnectorError):
                self.client.call(method)
        self.client.opener.open.assert_not_called()

    def test_write_disabled_for_all_write_tools(self):
        self.response({"result": True})
        for name, args in [("bitrix24_write_method", {"method": "tasks.task.add"}),
                           ("bitrix24_create_task", {"title": "Synthetic", "responsible_id": 1}),
                           ("bitrix24_add_task_comment", {"task_id": 1, "text": "Synthetic"})]:
            with self.subTest(tool=name):
                self.assertTrue(m.call_tool(self.client, name, args)["isError"])
        self.client.opener.open.assert_not_called()

    def test_write_cannot_be_enabled_with_model_boolean(self):
        result = m.call_tool(self.client, "bitrix24_write_method", {"method": "tasks.task.add", "confirmed": True})
        self.assertTrue(result["isError"])

    def test_enabled_write_preserves_params(self):
        self.client.writes = True
        self.response({"result": {"task": {"id": "99"}}})
        result = m.call_tool(self.client, "bitrix24_create_task", {"title": "Тест", "responsible_id": 1, "group_id": 2})
        self.assertFalse(result["isError"])
        request = self.client.opener.open.call_args.args[0]
        self.assertTrue(request.full_url.endswith("tasks.task.add.json"))
        self.assertEqual(json.loads(request.data)["fields"], {"TITLE": "Тест", "RESPONSIBLE_ID": 1, "GROUP_ID": 2})

    def test_unknown_method_through_write_tool(self):
        self.client.writes = True
        self.response({"result": []})
        self.assertFalse(m.call_tool(self.client, "bitrix24_write_method", {"method": "custom.module.list"})["isError"])

    def test_batch_rejected_even_with_write_enabled(self):
        self.client.writes = True
        self.response({"result": True})
        with self.assertRaisesRegex(m.ConnectorError, "batch"):
            self.client.call("batch", {"cmd": {"delete": "tasks.task.delete?taskId=1"}}, write=True)
        self.client.opener.open.assert_not_called()

    def test_method_cannot_change_url(self):
        self.response({"result": True})
        for method in ["https://evil.example", "//evil", "../scope", "scope?x=y", "scope#x", "scope%2fdelete", "scope\n"]:
            with self.assertRaises(m.ConnectorError):
                self.client.call(method)
        self.client.opener.open.assert_not_called()

    def test_api_error_suppresses_secret_and_raw_description(self):
        self.response({"error": "insufficient_scope", "error_description": HOOK})
        result = m.call_tool(self.client, "bitrix24_call_method", {"method": "profile"})
        self.assertIn("insufficient_scope", str(result))
        self.assertNotIn("synthetic_secret_123456", str(result))

    def test_http_error_suppresses_secrets(self):
        self.client.opener.open = Mock(side_effect=urllib.error.HTTPError(HOOK, 401, HOOK, {},
            io.BytesIO(json.dumps({"error": "INVALID_CREDENTIALS", "error_description": HOOK}).encode())))
        result = m.call_tool(self.client, "bitrix24_call_method", {"method": "profile"})
        self.assertIn("INVALID_CREDENTIALS", str(result))
        self.assertNotIn("synthetic_secret_123456", str(result))

    def test_even_error_code_cannot_echo_secret(self):
        self.response({"error": "synthetic_secret_123456"})
        result = m.call_tool(self.client, "bitrix24_call_method", {"method": "profile"})
        self.assertTrue(result["isError"])
        self.assertNotIn("synthetic_secret_123456", str(result))

    def test_no_write_retry_after_timeout(self):
        self.client.writes = True
        self.client.opener.open = Mock(side_effect=TimeoutError(HOOK))
        result = m.call_tool(self.client, "bitrix24_write_method", {"method": "tasks.task.add"})
        self.assertTrue(result["isError"])
        self.assertIn("verify remote state", str(result))
        self.assertNotIn("synthetic_secret_123456", str(result))
        self.assertEqual(self.client.opener.open.call_count, 1)

    def test_response_redacts_echoed_webhook(self):
        self.response({"result": {"link": HOOK, "array": [HOOK], HOOK: "value"}})
        self.assertNotIn("synthetic_secret_123456", json.dumps(self.client.call("profile")))

    def test_redirects_disabled(self):
        self.assertIsNone(m.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example/"))

    def test_response_limit_is_explicit_not_truncation(self):
        response = self.response({})
        response.read.return_value = b"x" * (m.MAX_BYTES + 1)
        with self.assertRaisesRegex(m.ConnectorError, "No partial"):
            self.client.call("profile")

    def test_status_no_network_or_secret(self):
        self.client.opener.open = Mock()
        result = m.call_tool(self.client, "bitrix24_status", {})
        self.assertNotIn("synthetic_secret_123456", str(result))
        self.assertIn("https://portal.example.org", str(result))
        self.client.opener.open.assert_not_called()

    def test_missing_config_supports_status_and_discovery(self):
        c = m.Client(Path(self.tmp.name) / "missing.json")
        self.assertFalse(c.status()["configured"])
        self.assertTrue(m.call_tool(c, "bitrix24_call_method", {"method": "profile"})["isError"])

    def test_invalid_config_fails_closed(self):
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaises(m.ConnectorError):
            m.Client(self.path)

    def test_config_permissions_posix(self):
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_argument_validation(self):
        for args in [{"task_id": True, "text": "x"}, {"task_id": 0, "text": "x"},
                     {"task_id": 1, "text": " "}, {"task_id": 1}, [], None]:
            self.assertTrue(m.call_tool(self.client, "bitrix24_add_task_comment", args)["isError"])

    def test_mcp_annotations_distinguish_writes(self):
        for tool in m.TOOLS:
            if tool["name"] in ("bitrix24_write_method", "bitrix24_create_task", "bitrix24_add_task_comment"):
                self.assertFalse(tool["annotations"]["readOnlyHint"])
                self.assertTrue(tool["annotations"]["destructiveHint"])

    def test_rpc_init_ping_notifications(self):
        server = m.Server(self.client)
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["error"]["code"], -32002)
        reply = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(reply["result"]["protocolVersion"], "2025-03-26")
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled"}))
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"], {})

    def test_stdio_process_real_handshake(self):
        messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "bitrix24_status", "arguments": {}}}]
        proc = subprocess.run([sys.executable, "-u", str(ROOT / "runtime/bitrix24_mcp_server.py"), "--config", str(self.path)],
                              input="\n".join(json.dumps(x) for x in messages) + "\n", text=True, encoding="utf-8", capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([x["id"] for x in replies], [1, 2, 3])
        self.assertEqual(len(replies[1]["result"]["tools"]), 7)
        self.assertNotIn("synthetic_secret_123456", proc.stdout + proc.stderr)

    def test_utf8_stdio_with_windows_style_legacy_encoding(self):
        path = Path(self.tmp.name) / "папка с пробелами" / "config.json"
        data = [{"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "bitrix24_status"}}]
        proc = subprocess.run([sys.executable, str(ROOT / "runtime/bitrix24_mcp_server.py"), "--config", str(path)],
                              input="\n".join(json.dumps(x) for x in data) + "\n", text=True, encoding="utf-8",
                              env={**os.environ, "PYTHONIOENCODING": "cp1252"}, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertFalse(replies[-1]["result"]["isError"])
        self.assertIn("папка с пробелами", proc.stdout)

    def test_cli_check_outputs_no_profile_data(self):
        with patch.object(m.Client, "call", return_value={"result": {"NAME": "Synthetic Personal Data"}}), \
             patch.object(sys, "argv", ["server", "--config", str(self.path), "--check"]), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(), 0)
        self.assertNotIn("Synthetic Personal Data", out.getvalue())
        self.assertNotIn("synthetic_secret_123456", out.getvalue())

    def test_configure_rejects_noninteractive_input(self):
        with patch.object(sys, "argv", ["server", "--config", str(self.path), "--configure"]), \
             patch("sys.stdin.isatty", return_value=False), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(), 1)

    def test_prepare_only_preserves_credentials(self):
        before = self.path.read_bytes()
        with patch.object(sys, "argv", ["install", "--prepare-only", "--config", str(self.path)]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(), 0)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual((self.path.parent / "runtime/bitrix24_mcp_server.py").read_bytes(),
                         (ROOT / "runtime/bitrix24_mcp_server.py").read_bytes())

    def test_installer_refuses_name_collision_before_writes(self):
        existing = [{"name": "bitrix24-local", "transport": {"command": "other", "args": ["other.py"]}}]
        with patch.object(sys, "argv", ["install", "--config", str(self.path), "--codex", "codex"]), \
             patch.object(install, "run_codex", return_value=Mock(returncode=0, stdout=json.dumps(existing))), \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            install.main()
        self.assertFalse((self.path.parent / "runtime").exists())

    def test_installer_registration_uses_interpreter_and_exact_paths(self):
        run = Mock(side_effect=[Mock(returncode=0, stdout="[]"), Mock(returncode=0)])
        with patch.object(sys, "argv", ["install", "--config", str(self.path), "--codex", "codex"]), \
             patch.object(install, "run_codex", run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(), 0)
        args = run.call_args.args[1]
        self.assertEqual(args[:5], ["mcp", "add", "bitrix24-local", "--", sys.executable])
        self.assertEqual(args[-2:], ["--config", str(self.path.resolve())])

    def test_manifests_match_runtime(self):
        portable = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        compat = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(portable["version"], m.VERSION)
        self.assertEqual(portable["name"], compat["name"])
        self.assertEqual(portable["version"], compat["version"])
        self.assertEqual(portable["extensions"]["com.openai"]["interface"], compat["interface"])
        self.assertLessEqual(len(compat["interface"]["shortDescription"]), 30)


if __name__ == "__main__":
    unittest.main()
