import sqlite3
import json
import pathlib
from datetime import datetime
from typing import Optional

DB_DIR = pathlib.Path.home() / ".pnpmonitor"
DB_PATH = DB_DIR / "state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitored_pages (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    url      TEXT UNIQUE NOT NULL,
    label    TEXT NOT NULL DEFAULT '',
    enabled  INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS page_states (
    url          TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    html_blob    BLOB,
    last_checked TEXT NOT NULL,
    last_changed TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publication_cache (
    position     INTEGER PRIMARY KEY,
    url          TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    doc_number   TEXT NOT NULL DEFAULT '',
    date         TEXT NOT NULL DEFAULT '',
    authors_json TEXT NOT NULL DEFAULT '[]',
    fetched_at   TEXT NOT NULL
);
"""

_DEFAULTS = {
    "check_interval_minutes": "60",
    "notify_on_change": "true",
}


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        for key, value in _DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()


class StorageManager:
    def __init__(self) -> None:
        init_db()

    # ── pages ─────────────────────────────────────────────────────────────

    def add_page(self, url: str, label: str) -> None:
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO monitored_pages (url, label, added_at) VALUES (?, ?, ?)",
                (url, label, datetime.now().isoformat()),
            )
            conn.commit()

    def remove_page(self, url: str) -> None:
        with _connect() as conn:
            conn.execute("DELETE FROM monitored_pages WHERE url = ?", (url,))
            conn.execute("DELETE FROM page_states WHERE url = ?", (url,))
            conn.commit()

    def get_monitored_pages(self) -> list[dict]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT id, url, label, enabled, added_at FROM monitored_pages ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_page_label(self, url: str, label: str) -> None:
        with _connect() as conn:
            conn.execute(
                "UPDATE monitored_pages SET label = ? WHERE url = ?", (label, url)
            )
            conn.commit()

    # ── page states ────────────────────────────────────────────────────────

    def get_last_state(self, url: str) -> tuple[Optional[str], Optional[str]]:
        with _connect() as conn:
            row = conn.execute(
                "SELECT content_hash, html_blob FROM page_states WHERE url = ?", (url,)
            ).fetchone()
        if row is None:
            return None, None
        html = row["html_blob"].decode("utf-8", errors="replace") if row["html_blob"] else None
        return row["content_hash"], html

    def update_state(self, url: str, content_hash: str, html: str) -> None:
        now = datetime.now().isoformat()
        old_hash, _ = self.get_last_state(url)
        changed_at = now if (old_hash and old_hash != content_hash) else None
        with _connect() as conn:
            conn.execute(
                """INSERT INTO page_states (url, content_hash, html_blob, last_checked, last_changed)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(url) DO UPDATE SET
                       content_hash = excluded.content_hash,
                       html_blob    = excluded.html_blob,
                       last_checked = excluded.last_checked,
                       last_changed = COALESCE(excluded.last_changed, last_changed)""",
                (url, content_hash, html.encode("utf-8"), now, changed_at),
            )
            conn.commit()

    def count_changed_pages(self) -> int:
        with _connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM page_states WHERE last_changed IS NOT NULL"
            ).fetchone()
        return row[0] if row else 0

    def clear_last_changed(self, url: str) -> None:
        with _connect() as conn:
            conn.execute(
                "UPDATE page_states SET last_changed = NULL WHERE url = ?", (url,)
            )
            conn.commit()

    def get_page_status(self, url: str) -> dict:
        with _connect() as conn:
            row = conn.execute(
                "SELECT last_checked, last_changed FROM page_states WHERE url = ?", (url,)
            ).fetchone()
        if row is None:
            return {"last_checked": None, "last_changed": None}
        return dict(row)

    # ── publication cache ──────────────────────────────────────────────────

    def save_pub_cache(self, pubs: list[dict]) -> None:
        """Replace the full cache with a new list."""
        now = datetime.now().isoformat()
        with _connect() as conn:
            conn.execute("DELETE FROM publication_cache")
            conn.executemany(
                "INSERT INTO publication_cache "
                "(position, url, title, doc_number, date, authors_json, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (i, p["url"], p.get("title", ""), p.get("doc_number", ""),
                     p.get("date", ""), p.get("authors_json", "[]"), now)
                    for i, p in enumerate(pubs)
                ],
            )
            conn.commit()

    def append_pub_cache(self, pubs: list[dict]) -> None:
        """Append new publications to the existing cache."""
        now = datetime.now().isoformat()
        with _connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM publication_cache"
            ).fetchone()
            start = row[0] + 1
            conn.executemany(
                "INSERT OR IGNORE INTO publication_cache "
                "(position, url, title, doc_number, date, authors_json, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (start + i, p["url"], p.get("title", ""), p.get("doc_number", ""),
                     p.get("date", ""), p.get("authors_json", "[]"), now)
                    for i, p in enumerate(pubs)
                ],
            )
            conn.commit()

    def load_pub_cache(self) -> tuple[list[dict], Optional[str]]:
        """Return (rows, fetched_at_iso) or ([], None) if empty."""
        with _connect() as conn:
            rows = conn.execute(
                "SELECT url, title, doc_number, date, authors_json, fetched_at "
                "FROM publication_cache ORDER BY position"
            ).fetchall()
        if not rows:
            return [], None
        return [dict(r) for r in rows], rows[0]["fetched_at"]

    # ── settings ───────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        with _connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()
