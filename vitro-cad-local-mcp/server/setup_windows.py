"""Validate the portal and personal credentials, then save them for this Windows user."""
from __future__ import annotations

import getpass
import json
import os
import sys
import uuid

from credential_store import CredentialError, clear, load, save
from vitro_api import VitroError, login, validate_portal_url


def main() -> int:
    if os.name != "nt":
        print("Для этого выпуска требуется Windows.", file=sys.stderr)
        return 1
    if "--clear" in sys.argv[1:]:
        clear()
        print("Сохранённый вход удалён.")
        return 0
    if "--check-saved" in sys.argv[1:]:
        try:
            data = load()
            login(data["portal"], data["login"], data["password"])
            return 0
        except (CredentialError, VitroError):
            return 1
    if "--credential-stdin" in sys.argv[1:]:
        try:
            data = json.loads(sys.stdin.buffer.readline().decode("utf-8"))
            portal = validate_portal_url(data["portal"])
            login_name = data["login"].strip()
            password = data["password"]
            registry = data.get("registry_list_id", "").strip()
        except (ValueError, KeyError, TypeError, AttributeError, VitroError) as exc:
            print(f"Проверьте адрес портала и заполнение полей: {exc}", file=sys.stderr)
            return 1
    else:
        portal = input("HTTPS-адрес вашего портала Vitro-CAD: ").strip()
        login_name = input("Логин или e-mail: ").strip()
        password = getpass.getpass("Пароль (символы скрыты): ")
        registry = input("GUID реестра проектов (если известен, иначе Enter): ").strip()
    try:
        portal = validate_portal_url(portal)
        if not isinstance(password, str) or not login_name or not password:
            raise ValueError("Логин и пароль обязательны.")
        if registry:
            registry = str(uuid.UUID(registry))
        _, user = login(portal, login_name, password)
        save(portal, login_name, password, registry)
    except (ValueError, VitroError, CredentialError) as exc:
        print(f"Настройка не завершена: {exc}", file=sys.stderr)
        return 1
    print(f"Портал: {portal}")
    print(f"Вход подтверждён: {user.get('name') or user.get('email') or user.get('id')}.")
    print("Действия ограничены правами этой учётной записи Vitro-CAD.")
    if registry:
        print("Реестр проектов настроен.")
    else:
        print("Реестр проектов не указан; остальные инструменты доступны по известным идентификаторам.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
