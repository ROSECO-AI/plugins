"""Small Vitro-CAD MP REST client. Never returns authentication secrets."""

from __future__ import annotations

import json
import mimetypes
import ssl
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit

def validate_portal_url(value: str) -> str:
    """Accept only a complete HTTPS portal origin (no embedded credentials or API path)."""
    if not isinstance(value, str) or value != value.strip():
        raise VitroError("Введите полный HTTPS-адрес портала без пробелов.")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise VitroError("Нужен адрес вида https://portal.example.org/ без пути, параметров и пароля.")
    try:
        port = parsed.port
    except ValueError:
        raise VitroError("Проверьте порт в адресе портала.") from None
    host = parsed.hostname
    if any(c.isspace() for c in host):
        raise VitroError("Проверьте имя портала.")
    return f"https://{parsed.netloc}".rstrip("/")


class VitroError(RuntimeError):
    pass


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _https_context():
    if sys.platform == "win32":
        # Use Windows' certificate-chain verification, as desktop browsers do.
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


def _request(base_url: str, path: str, *, token: str | None = None, body: Any = None,
             multipart: tuple[dict[str, str], list[tuple[str, Path]]] | None = None,
             binary: bool = False, method: str = "POST") -> Any:
    headers: dict[str, str] = {}
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if multipart is not None:
        fields, files = multipart
        boundary = f"----vitro-{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks += [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"), b"\r\n",
            ]
        for name, file_path in files:
            mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            chunks += [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{file_path.name}"\r\n'.encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                file_path.read_bytes(), b"\r\n",
            ]
        chunks.append(f"--{boundary}--\r\n".encode())
        payload = b"".join(chunks)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    if token:
        headers["Authorization"] = token  # Vitro uses the raw token, without Bearer.
    base_url = validate_portal_url(base_url)
    if not path.startswith("api/") or ".." in path or "?" in path or "#" in path:
        raise VitroError("Некорректный путь API.")
    req = request.Request(f"{base_url}/{path}", data=payload, headers=headers, method=method)
    # Never forward the raw Vitro token to a redirect destination.
    opener = request.build_opener(_NoRedirect, request.HTTPSHandler(context=_https_context()))
    try:
        with opener.open(req, timeout=60) as response:
            data = response.read()
    except error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise VitroError("Портал перенаправил API-запрос. Проверьте точный адрес портала; токен не передан другому сайту.") from None
        raise VitroError(f"Vitro вернул HTTP {exc.code} для {path}.") from None
    except error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            detail = getattr(exc.reason, "verify_message", "")
            suffix = f" Причина: {detail}." if detail else ""
            raise VitroError(
                "Не удалось проверить HTTPS-сертификат портала Vitro на этом компьютере. "
                f"Проверьте дату и время Windows и откройте {base_url}/ "
                "в браузере без предупреждения о сертификате; если проблема остается, "
                "обратитесь к администратору своего портала." + suffix
            ) from None
        raise VitroError(f"Нет соединения с порталом Vitro ({type(exc.reason).__name__}).") from None
    if binary:
        return data
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise VitroError("Vitro вернул ответ не в ожидаемом формате JSON.") from None


def login(base_url: str, login_name: str, password: str) -> tuple[str, dict[str, Any]]:
    response = _request(base_url, "api/security/Login", body={"login": login_name, "password": password})
    if not isinstance(response, dict):
        raise VitroError("Vitro не вернул объект сессии.")
    status = response.get("status")
    if status == 2:
        raise VitroError("Для учетной записи включена 2FA. Нужна настройка штатного TwoFactorLogin для этой инсталляции.")
    if status not in (1, None) or not response.get("token"):
        raise VitroError(f"Вход не завершен: статус сессии {status!r}.")
    user = response.get("user")
    if not isinstance(user, dict):
        raise VitroError("Vitro не вернул сведения о вошедшем пользователе.")
    return str(response["token"]), user


class Client:
    def __init__(self, base_url: str, login_name: str, password: str):
        self.base_url = validate_portal_url(base_url)
        self.login_name = login_name
        self.password = password
        self.token: str | None = None
        self.user: dict[str, Any] | None = None

    def authenticate(self) -> dict[str, Any]:
        self.token, self.user = login(self.base_url, self.login_name, self.password)
        return {key: self.user.get(key) for key in ("id", "name", "email", "isAdmin", "license")}

    def call(self, path: str, *, body: Any = None,
             multipart: tuple[dict[str, str], list[tuple[str, Path]]] | None = None,
             binary: bool = False, method: str = "POST",
             retry_on_unauthorized: bool = True) -> Any:
        if not self.token:
            self.authenticate()
        try:
            return _request(self.base_url, path, token=self.token, body=body, multipart=multipart, binary=binary, method=method)
        except VitroError as exc:
            if "HTTP 401" not in str(exc):
                raise
            self.authenticate()
            if not retry_on_unauthorized:
                raise VitroError("Сессия обновлена после HTTP 401. Проверьте состояние элемента перед повтором изменения.") from None
            return _request(self.base_url, path, token=self.token, body=body, multipart=multipart, binary=binary, method=method)
