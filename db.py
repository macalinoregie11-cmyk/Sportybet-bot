"""Tiny SQLite wrapper for tracked matches."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tracked.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            start_time INTEGER,
            seen_live INTEGER DEFAULT 0,
            notified INTEGER DEFAULT 0,
            last_home_score TEXT,
            last_away_score TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_tracked_match(chat_id, event_id, home_team, away_team, start_time):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO tracked_matches
           (chat_id, event_id, home_team, away_team, start_time)
           VALUES (?, ?, ?, ?, ?)""",
        (str(chat_id), event_id, home_team, away_team, start_time),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def list_tracked_matches(chat_id, only_pending=True):
    conn = get_conn()
    query = "SELECT * FROM tracked_matches WHERE chat_id = ?"
    params = [str(chat_id)]
    if only_pending:
        query += " AND notified = 0"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_pending_matches():
    """All matches (any chat) not yet notified as finished."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tracked_matches WHERE notified = 0"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_tracked_match(row_id, chat_id):
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM tracked_matches WHERE id = ? AND chat_id = ?",
        (row_id, str(chat_id)),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted > 0


def mark_seen_live(row_id, home_score=None, away_score=None):
    conn = get_conn()
    conn.execute(
        """UPDATE tracked_matches
           SET seen_live = 1, last_home_score = ?, last_away_score = ?
           WHERE id = ?""",
        (home_score, away_score, row_id),
    )
    conn.commit()
    conn.close()


def mark_notified(row_id):
    conn = get_conn()
    conn.execute("UPDATE tracked_matches SET notified = 1 WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
