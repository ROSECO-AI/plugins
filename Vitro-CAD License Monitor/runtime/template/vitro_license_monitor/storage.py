from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .collector import LicenseReading


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_at TEXT NOT NULL,
                    web_active INTEGER NOT NULL,
                    pro_active INTEGER NOT NULL,
                    without_active_license INTEGER NOT NULL,
                    total_users INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS samples_observed_at_idx ON samples(observed_at);
                """
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, reading: LicenseReading) -> dict[str, Any]:
        values = (
            reading.observed_at.isoformat(),
            reading.web_active,
            reading.pro_active,
            reading.without_active_license,
            reading.total_users,
            reading.duration_ms,
        )
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO samples (
                    observed_at, web_active, pro_active, without_active_license,
                    total_users, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        return {"id": cursor.lastrowid, **dict(zip(
            ("observed_at", "web_active", "pro_active", "without_active_license", "total_users", "duration_ms"),
            values,
        ))}

    def latest(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM samples ORDER BY observed_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def since(self, start: datetime, limit: int = 10000) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM samples WHERE observed_at >= ? ORDER BY observed_at ASC LIMIT ?",
                (start.isoformat(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def columns(self) -> tuple[str, ...]:
        with self.connect() as connection:
            rows = connection.execute("PRAGMA table_info(samples)").fetchall()
        return tuple(str(row["name"]) for row in rows)
