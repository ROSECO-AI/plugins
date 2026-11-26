from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _safe_error(payload: str) -> str:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return "non-JSON response"
    if not isinstance(value, dict):
        return "unexpected response"
    safe: dict[str, Any] = {}
    for key in ("status", "title", "type", "traceId"):
        if value.get(key) is not None:
            safe[key] = value[key]
    exception = value.get("exception")
    if isinstance(exception, dict):
        safe_exception = {
            key: exception[key]
            for key in ("licenseType", "source", "hResult")
            if exception.get(key) is not None
        }
        if safe_exception:
            safe["exception"] = safe_exception
    return json.dumps(safe, ensure_ascii=False) if safe else "server rejected the request"


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = token
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as response:
            payload = response.read()
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {exc.code}: {_safe_error(raw)}", exc.code) from exc
    except error.URLError as exc:
        raise ApiError(f"Network error: {exc.reason}") from exc
    if not payload:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError("Vitro-CAD returned invalid JSON") from exc


def login(base_url: str, login_name: str, password: str) -> dict[str, Any]:
    response = request_json(
        "POST",
        api_url(base_url, "api/security/Login"),
        body={"login": login_name, "password": password},
    )
    if not isinstance(response, dict):
        raise ApiError("Login response is not an object")
    status = response.get("status")
    if status == 2:
        raise ApiError("Two-factor authentication is required and is not supported in version 1.0.0")
    if status == 3:
        raise ApiError("Vitro-CAD requires initial password setup")
    if status == 4:
        raise ApiError("Vitro-CAD requires a password change")
    if status not in (None, 1) or not response.get("token"):
        raise ApiError("Vitro-CAD login did not produce an active session")
    return response


def lookup_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        fields = value.get("fieldValueMap")
        if isinstance(fields, dict):
            candidate = fields.get("name")
            if candidate is not None:
                return str(candidate)
        candidate = value.get("name")
        if candidate is not None:
            return str(candidate)
    return None


def list_id_from_login(response: dict[str, Any]) -> str:
    user = response.get("user")
    item = user.get("item") if isinstance(user, dict) else None
    value = item.get("listId") if isinstance(item, dict) else None
    return str(value or "")
