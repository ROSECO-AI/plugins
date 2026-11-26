from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .api import ApiError, api_url, lookup_name, request_json
from .config import Settings


@dataclass(frozen=True)
class LicenseReading:
    observed_at: datetime
    web_active: int
    pro_active: int
    without_active_license: int
    total_users: int
    duration_ms: int


def discover_active_license_field(items: list[dict[str, Any]]) -> str:
    preferred = "principal_active_license_type"
    if any(preferred in (item.get("fieldValueMap") or {}) for item in items):
        return preferred
    candidates: set[str] = set()
    for item in items:
        fields = item.get("fieldValueMap") or {}
        for key, value in fields.items():
            name = (lookup_name(value) or "").upper()
            if name in {"WEB", "PRO"}:
                candidates.add(str(key))
    if len(candidates) == 1:
        return next(iter(candidates))
    names = ", ".join(sorted(candidates)) or "none"
    raise ApiError(f"Could not identify one active-license field; candidates: {names}")


def _user_items(items: list[dict[str, Any]], settings: Settings, license_field: str) -> list[dict[str, Any]]:
    named = [
        item
        for item in items
        if (lookup_name((item.get("fieldValueMap") or {}).get(settings.content_type_field)) or "").casefold()
        == settings.user_content_type_name.casefold()
    ]
    if named:
        return named
    raise ApiError("The selected list could not be validated as a complete user list")


def collect(settings: Settings, token: str) -> tuple[LicenseReading, str]:
    if not settings.user_list_id:
        raise ApiError("User list ID is missing. Run login again.")
    started = time.monotonic()
    response = request_json(
        "POST",
        api_url(settings.base_url, f"api/item/getRecursive/{settings.user_list_id}"),
        token=token,
    )
    if not isinstance(response, list) or not all(isinstance(item, dict) for item in response):
        raise ApiError("Vitro-CAD user-list response is not an array of objects")
    license_field = settings.active_license_field or discover_active_license_field(response)
    users = _user_items(response, settings, license_field)
    counts = {"WEB": 0, "PRO": 0, "NONE": 0}
    unknown: set[str] = set()
    for user in users:
        fields = user.get("fieldValueMap") or {}
        value = (lookup_name(fields.get(license_field)) or "").strip().upper()
        if value in {"WEB", "PRO"}:
            counts[value] += 1
        elif not value:
            counts["NONE"] += 1
        else:
            unknown.add(value)
    if unknown:
        raise ApiError(f"Unknown active-license values were found ({len(unknown)} distinct values)")
    total = len(users)
    if total == 0 or counts["WEB"] + counts["PRO"] + counts["NONE"] != total:
        raise ApiError("Aggregate validation failed")
    return (
        LicenseReading(
            observed_at=datetime.now(timezone.utc),
            web_active=counts["WEB"],
            pro_active=counts["PRO"],
            without_active_license=counts["NONE"],
            total_users=total,
            duration_ms=round((time.monotonic() - started) * 1000),
        ),
        license_field,
    )
