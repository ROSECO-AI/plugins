"""Local stdio MCP bridge to Vitro-CAD MP for the signed-in Windows user."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from credential_store import CredentialError, load, record_delete, record_restore, was_deleted
from vitro_api import Client, VitroError

client: Client | None = None


def guid(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Ожидался корректный GUID элемента Vitro.") from None


def active_client() -> Client:
    global client
    if client is None:
        saved = load()
        client = Client(saved["portal"], saved["login"], saved["password"])
    return client


def name_of(item: dict[str, Any]) -> str:
    value = (item.get("fieldValueMap") or {}).get("name")
    if isinstance(value, dict):
        value = (value.get("fieldValueMap") or {}).get("name") or value.get("name")
    return str(value or item.get("name") or "")


def limit_items(value: Any, maximum: int) -> Any:
    if not isinstance(value, list):
        return value
    maximum = max(1, min(maximum, 500))
    return {"total_returned_by_vitro": len(value), "items": value[:maximum],
            "truncated": len(value) > maximum}


TOOLS = [
    ("vitro_whoami", "Проверить вход и показать текущую учетную запись Vitro без токена.", {}),
    ("vitro_list_projects", "Прочитать реестр проектов, если его GUID указан при установке или в аргументе; доступ к папкам проверять отдельно.",
     {"registry_list_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
    ("vitro_get_item", "Прочитать элемент Vitro по GUID с правами текущего пользователя.",
     {"item_id": {"type": "string"}}),
    ("vitro_get_children", "Прочитать непосредственные дочерние элементы папки или списка.",
     {"parent_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
    ("vitro_get_recursive", "Прочитать дерево дочерних элементов; вывод ограничен первыми 500 записями.",
     {"root_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
    ("vitro_get_list_metadata", "Прочитать метаданные списка Vitro по GUID.",
     {"list_id": {"type": "string"}}),
    ("vitro_get_content_types", "Прочитать типы элементов и поля списка перед созданием или обновлением.",
     {"list_id": {"type": "string"}}),
    ("vitro_update_item", "Создать или обновить один элемент через api/item/update; предварительно изучить его схему и права.",
     {"item": {"type": "object"}}),
    ("vitro_upload_file", "Создать файл Vitro из локального файла через api/item/update.",
     {"path": {"type": "string"}, "list_id": {"type": "string"},
      "content_type_id": {"type": "string"}, "parent_id": {"type": "string"},
      "name": {"type": "string"}}),
    ("vitro_download_file", "Скачать текущую версию файла Vitro в указанную локальную папку.",
     {"item_id": {"type": "string"}, "output_path": {"type": "string"}}),
    ("vitro_delete_item", "Переместить один элемент в корзину Vitro после сверки GUID и имени. Повторное удаление может быть окончательным.",
     {"item_id": {"type": "string"}, "expected_name": {"type": "string"},
      "expected_parent_id": {"type": "string"}, "confirm_item_id": {"type": "string"}}),
    ("vitro_restore_item", "Восстановить элемент из корзины Vitro по GUID.",
     {"item_id": {"type": "string"}}),
]

REQUIRED = {
    "vitro_get_item": ["item_id"], "vitro_get_children": ["parent_id"],
    "vitro_get_recursive": ["root_id"], "vitro_get_list_metadata": ["list_id"],
    "vitro_get_content_types": ["list_id"], "vitro_update_item": ["item"],
    "vitro_upload_file": ["path", "list_id", "content_type_id", "parent_id"],
    "vitro_download_file": ["item_id", "output_path"],
    "vitro_delete_item": ["item_id", "expected_name", "expected_parent_id", "confirm_item_id"],
    "vitro_restore_item": ["item_id"],
}


def tool_specs() -> list[dict[str, Any]]:
    return [{"name": name, "description": description,
             "inputSchema": {"type": "object", "properties": fields,
                             "required": REQUIRED.get(name, []), "additionalProperties": False}}
            for name, description, fields in TOOLS]


def call_tool(name: str, args: dict[str, Any]) -> Any:
    if name not in {row[0] for row in TOOLS}:
        raise ValueError(f"Неизвестный инструмент: {name}")
    api = active_client()
    if name == "vitro_whoami":
        return {"portal": api.base_url, "user": api.authenticate()}
    if name == "vitro_list_projects":
        registry = args.get("registry_list_id") or load().get("registry_list_id")
        if not registry:
            raise ValueError("В этом портале GUID реестра проектов не задан. Укажите registry_list_id или откройте доступный список через vitro_get_children.")
        return limit_items(api.call(f"api/item/getList/{guid(registry)}"),
                           int(args.get("limit", 100)))
    if name == "vitro_get_item":
        return api.call(f"api/item/get/{guid(args['item_id'])}")
    if name == "vitro_get_children":
        return limit_items(api.call(f"api/item/getList/{guid(args['parent_id'])}"),
                           int(args.get("limit", 100)))
    if name == "vitro_get_recursive":
        return limit_items(api.call(f"api/item/getRecursive/{guid(args['root_id'])}"),
                           int(args.get("limit", 100)))
    if name == "vitro_get_list_metadata":
        return api.call(f"api/list/get/{guid(args['list_id'])}")
    if name == "vitro_get_content_types":
        return api.call(f"api/contenttype/getByList/{guid(args['list_id'])}")
    if name == "vitro_update_item":
        if not isinstance(args["item"], dict) or not args["item"]:
            raise ValueError("Нужен непустой объект элемента.")
        item = dict(args["item"])
        if item.get("id"):
            guid(item["id"])
            current = api.call(f"api/item/get/{guid(item['id'])}")
            for field, current_field in (("list_id", "listId"),
                                         ("content_type_id", "contentTypeId"),
                                         ("parent_id", "parentId")):
                actual = current.get(current_field)
                if item.get(field) and guid(item[field]) != guid(actual):
                    raise ValueError(f"{field} не совпадает с текущим элементом.")
                item[field] = actual
        elif item.get("parent_id"):
            guid(item["parent_id"])
            parent = api.call(f"api/item/get/{guid(item['parent_id'])}")
            actual_list_id = parent.get("listId")
            if item.get("list_id") and guid(item["list_id"]) != guid(actual_list_id):
                raise ValueError("list_id не совпадает со списком родительской папки.")
            item["list_id"] = actual_list_id
            if not item.get("content_type_id"):
                raise ValueError("Для создания укажите content_type_id после чтения типов элементов списка.")
        else:
            raise ValueError("Укажите id для обновления или parent_id для создания.")
        if not item.get("list_id") or not item.get("content_type_id") or not item.get("parent_id"):
            raise ValueError("Не удалось определить список, тип элемента и родителя для записи.")
        fields = {"itemListJson": json.dumps([item], ensure_ascii=False)}
        return api.call("api/item/update", multipart=(fields, []), retry_on_unauthorized=False)
    if name == "vitro_upload_file":
        path = Path(args["path"]).expanduser().resolve()
        if not path.is_file():
            raise ValueError("Локальный файл не найден.")
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Этот инструмент загружает файлы до 100 МиБ.")
        parent_id = guid(args["parent_id"])
        parent = api.call(f"api/item/get/{parent_id}")
        if guid(args["list_id"]) != guid(parent.get("listId")):
            raise ValueError("list_id не совпадает со списком родительской папки.")
        item = {"list_id": guid(args["list_id"]),
                "content_type_id": guid(args["content_type_id"]),
                "parent_id": parent_id, "name": args.get("name") or path.name, "file": 0}
        fields = {"itemListJson": json.dumps([item], ensure_ascii=False)}
        return api.call("api/item/update", multipart=(fields, [("fileList", path)]), retry_on_unauthorized=False)
    if name == "vitro_download_file":
        item_id = guid(args["item_id"])
        item = api.call(f"api/item/get/{item_id}")
        value = (item.get("fieldValueMap") or {}).get("version")
        version = ((value.get("fieldValueMap") or {}).get("name") or value.get("id")) if isinstance(value, dict) else value
        if not version:
            raise ValueError("У элемента нет текущей версии файла.")
        endpoint = f"api/file/getbyitemid/{item_id}/{quote(str(version), safe='')}"
        try:
            data = api.call(endpoint, binary=True)
        except VitroError as exc:
            if "HTTP 405" not in str(exc):
                raise
            data = api.call(endpoint, binary=True, method="GET")
        output = Path(args["output_path"]).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        return {"path": str(output), "size_bytes": len(data), "item_id": item_id}
    if name == "vitro_delete_item":
        item_id = guid(args["item_id"])
        if guid(args["confirm_item_id"]) != item_id:
            raise ValueError("confirm_item_id не совпадает с item_id.")
        if was_deleted(f"{api.base_url}:{item_id}"):
            raise ValueError("Этот GUID уже удалялся через плагин; повторное удаление заблокировано.")
        item = api.call(f"api/item/get/{item_id}")
        actual_name = name_of(item)
        if not actual_name or actual_name != args["expected_name"]:
            raise ValueError("Имя элемента изменилось или не совпадает с expected_name.")
        if guid(item.get("parentId")) != guid(args["expected_parent_id"]):
            raise ValueError("Родитель элемента изменился или не совпадает с expected_parent_id.")
        if item.get("isDeleted") is True:
            raise ValueError("Элемент уже в корзине; повторное удаление запрещено.")
        result = api.call("api/item/delete", body=[{"id": item_id}], retry_on_unauthorized=False)
        record_delete(f"{api.base_url}:{item_id}")
        return result
    if name == "vitro_restore_item":
        item_id = guid(args["item_id"])
        result = api.call(f"api/item/restore/{item_id}", retry_on_unauthorized=False)
        record_restore(f"{api.base_url}:{item_id}")
        return result
    raise ValueError("Инструмент не реализован.")


def respond(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    if method is None:
        return None
    if method == "notifications/initialized":
        return None
    message_id = message.get("id")
    if message_id is None:
        return None
    try:
        if method == "initialize":
            result = {"protocolVersion": message.get("params", {}).get("protocolVersion", "2024-11-05"),
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "vitro-cad-local", "version": "1.0.0"},
                      "instructions": "Vitro-CAD запросы выполняются от имени текущей личной учетной записи и для настроенного портала. Сначала вызовите vitro_whoami. Не предполагайте наличие единого реестра проектов: его GUID задаётся отдельно для портала. Перед записью и удалением сверяйте элемент и права; согласуйте действие с пользователем. Не повторяйте удаление элемента: второй вызов может удалить его окончательно."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tool_specs()}
        elif method == "tools/call":
            params = message.get("params") or {}
            value = call_tool(params.get("name", ""), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}]}
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            return {"jsonrpc": "2.0", "id": message_id,
                    "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": message_id, "result": result}
    except (CredentialError, VitroError, ValueError, KeyError, TypeError, OSError) as exc:
        if method == "tools/call":
            return {"jsonrpc": "2.0", "id": message_id,
                    "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": message_id,
                "error": {"code": -32603, "message": str(exc)}}


def main() -> None:
    for line in sys.stdin.buffer:
        try:
            message = json.loads(line)
            response = respond(message)
            if response is not None:
                # MCP stdio requires UTF-8 even when Windows uses a legacy code page.
                sys.stdout.buffer.write(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
                sys.stdout.buffer.flush()
        except (ValueError, TypeError):
            # Keep stdout strictly for valid JSON-RPC messages.
            continue


if __name__ == "__main__":
    main()
