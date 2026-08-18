"""SQLite connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from ofertaks.database.schema import (
    MERCHANT_MIGRATION_COLUMNS,
    OFFER_MIGRATION_COLUMNS,
    POST_MIGRATION_SQL,
    SCHEMA_SQL,
    SCHEMA_VERSION,
)


class _ConnectionManager:
    def __init__(self, path: Path):
        self.path = path
        self.connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.connection is None:
            return
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
            self.connection = None


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> _ConnectionManager:
        return _ConnectionManager(self.path)

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._migrate_offer_columns(connection)
            self._migrate_merchant_columns(connection)
            connection.executescript(POST_MIGRATION_SQL)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _migrate_offer_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(offers)")
        }
        for column, definition in OFFER_MIGRATION_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE offers ADD COLUMN {column} {definition}")

    def _migrate_merchant_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(merchants)")
        }
        for column, definition in MERCHANT_MIGRATION_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE merchants ADD COLUMN {column} {definition}")
