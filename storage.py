"""Lightweight SQLite storage for history + analytics."""
import sqlite3
import time
from pathlib import Path
from contextlib import closing

DB_PATH = Path(__file__).parent / "qrzenbot.db"


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                kind       TEXT    NOT NULL,   -- 'generate' or 'scan'
                qr_type    TEXT,               -- URL / WiFi / Contact / ...
                label      TEXT,
                payload    TEXT,
                created_at REAL    NOT NULL
            )
            """
        )
        db.commit()


def log_event(user_id: int, kind: str, qr_type: str, label: str, payload: str) -> None:
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute(
            "INSERT INTO history (user_id, kind, qr_type, label, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, kind, qr_type, label, payload[:500], time.time()),
        )
        db.commit()


def recent_history(user_id: int, limit: int = 6) -> list[dict]:
    with closing(sqlite3.connect(DB_PATH)) as db:
        rows = db.execute(
            "SELECT kind, qr_type, label, payload, created_at FROM history "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        {"kind": r[0], "qr_type": r[1], "label": r[2], "payload": r[3], "created_at": r[4]}
        for r in rows
    ]


def analytics(user_id: int) -> dict:
    with closing(sqlite3.connect(DB_PATH)) as db:
        generated = db.execute(
            "SELECT COUNT(*) FROM history WHERE user_id=? AND kind='generate'",
            (user_id,),
        ).fetchone()[0]
        scanned = db.execute(
            "SELECT COUNT(*) FROM history WHERE user_id=? AND kind='scan'",
            (user_id,),
        ).fetchone()[0]
        month_ago = time.time() - 30 * 86400
        this_month = db.execute(
            "SELECT COUNT(*) FROM history WHERE user_id=? AND created_at>=?",
            (user_id, month_ago),
        ).fetchone()[0]
        by_type_rows = db.execute(
            "SELECT qr_type, COUNT(*) FROM history "
            "WHERE user_id=? AND kind='generate' AND qr_type IS NOT NULL "
            "GROUP BY qr_type ORDER BY COUNT(*) DESC",
            (user_id,),
        ).fetchall()
    return {
        "generated": generated,
        "scanned": scanned,
        "this_month": this_month,
        "by_type": [{"type": t, "count": c} for t, c in by_type_rows],
    }
