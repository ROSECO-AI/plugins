"""Per-Windows-user Vitro-CAD configuration protected by DPAPI."""
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


class CredentialError(RuntimeError):
    pass


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def state_dir() -> Path:
    if os.name != "nt" or not os.environ.get("APPDATA"):
        raise CredentialError("Нужна личная учётная запись Windows с APPDATA.")
    return Path(os.environ["APPDATA"]) / "vitro-cad-local-mcp"


def credential_path() -> Path:
    return state_dir() / "credentials.dpapi"


def _transform(payload: bytes, *, encrypt: bool) -> bytes:
    if os.name != "nt":
        raise CredentialError("DPAPI доступен только в Windows.")
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DataBlob), wintypes.LPCWSTR,
                                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(DataBlob)]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.POINTER(DataBlob)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(payload)
    source = DataBlob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = DataBlob()
    if encrypt:
        ok = crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output))
    if not ok:
        raise CredentialError("Windows не смогла защитить или прочитать настройки входа.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


def save(portal: str, login: str, password: str, registry_list_id: str = "") -> None:
    from vitro_api import validate_portal_url
    portal = validate_portal_url(portal)
    path = credential_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"portal": portal, "login": login, "password": password,
                          "registry_list_id": registry_list_id}).encode("utf-8")
    encrypted = _transform(payload, encrypt=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(encrypted)
    temporary.replace(path)


def load() -> dict[str, str]:
    from vitro_api import validate_portal_url
    path = credential_path()
    if not path.is_file():
        raise CredentialError("Для этой учётной записи Windows нет настроенного входа Vitro-CAD. Запустите установщик под этой же учётной записью.")
    try:
        value = json.loads(_transform(path.read_bytes(), encrypt=False).decode("utf-8"))
        portal = validate_portal_url(value["portal"])
        login, password = value["login"], value["password"]
        registry = value.get("registry_list_id", "")
        if not all(isinstance(x, str) for x in (login, password, registry)) or not login or not password:
            raise ValueError("Неверные настройки")
        return {"portal": portal, "login": login, "password": password, "registry_list_id": registry}
    except (OSError, ValueError, KeyError, UnicodeError, TypeError) as exc:
        raise CredentialError("Настройки входа повреждены или относятся к другой учётной записи Windows. Запустите установщик заново.") from exc


def clear() -> None:
    credential_path().unlink(missing_ok=True)


def _ledger_path() -> Path:
    return state_dir() / "deleted_ids.json"


def was_deleted(item_id: str) -> bool:
    path = _ledger_path()
    if not path.is_file():
        return False
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CredentialError("Журнал удалений повреждён; повторное удаление заблокировано.") from exc
    if not isinstance(values, list):
        raise CredentialError("Журнал удалений повреждён; повторное удаление заблокировано.")
    return item_id in values


def record_delete(item_id: str) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    values = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    if not isinstance(values, list):
        raise CredentialError("Журнал удалений повреждён; повторное удаление заблокировано.")
    if item_id not in values:
        values.append(item_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(values), encoding="utf-8")
    tmp.replace(path)


def record_restore(item_id: str) -> None:
    path = _ledger_path()
    if path.is_file():
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(values, list):
                raise ValueError()
        except (OSError, ValueError) as exc:
            raise CredentialError("Журнал удалений повреждён.") from exc
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps([v for v in values if v != item_id]), encoding="utf-8")
        tmp.replace(path)
