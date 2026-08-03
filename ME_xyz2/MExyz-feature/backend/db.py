"""SQLite connection and schema for ME.xyz."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DB = DATA_DIR / "me.db"
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB)))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT,
  nickname TEXT,
  avatar_url TEXT,
  email_verified INTEGER NOT NULL DEFAULT 0,
  oauth_provider TEXT,
  oauth_sub TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_verification_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT 'register',
  attempts INTEGER NOT NULL DEFAULT 0,
  consumed_at TEXT,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_codes_email
  ON email_verification_codes(email, created_at);

CREATE TABLE IF NOT EXISTS sessions (
  user_id TEXT NOT NULL,
  id TEXT NOT NULL,
  type TEXT NOT NULL,
  title TEXT,
  persona_id TEXT,
  gate_json TEXT,
  conversation_state_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, id)
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session
  ON messages(user_id, session_id, ts);

CREATE TABLE IF NOT EXISTS personas (
  id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  title TEXT,
  mood TEXT,
  accent TEXT,
  path TEXT,
  day TEXT,
  cost TEXT,
  system_prompt TEXT,
  source_session_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, id)
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  event_time TEXT,
  event TEXT,
  emotions_json TEXT,
  viewpoint TEXT,
  world TEXT,
  branch_id TEXT,
  source_session_id TEXT,
  evidence_json TEXT,
  event_time_iso TEXT,
  emotions_detail_json TEXT DEFAULT '[]',
  source_turn_id TEXT,
  parent_event_id TEXT,
  branch_origin_event_id TEXT,
  growth_summary TEXT,
  created_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_user
  ON events(user_id, world, branch_id);

CREATE TABLE IF NOT EXISTS mindmap_nodes (
  id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  label TEXT,
  kind TEXT,
  summary TEXT,
  source_session TEXT,
  event_id TEXT,
  world TEXT,
  branch_id TEXT,
  PRIMARY KEY (user_id, id)
);

CREATE TABLE IF NOT EXISTS mindmap_edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DB_PATH if DB_PATH.is_absolute() else Path(__file__).resolve().parent / DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    user_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    user_additions = {
        "email_verified": "INTEGER NOT NULL DEFAULT 0",
        "oauth_provider": "TEXT",
        "oauth_sub": "TEXT",
        "avatar_url": "TEXT",
    }
    for name, sql_type in user_additions.items():
        if name not in user_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {sql_type}")

    session_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "conversation_state_json" not in session_cols:
        conn.execute(
            "ALTER TABLE sessions ADD COLUMN conversation_state_json TEXT DEFAULT '{}'"
        )
    event_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()
    }
    additions = {
        "event_time_iso": "TEXT",
        "emotions_detail_json": "TEXT DEFAULT '[]'",
        "source_turn_id": "TEXT",
        "parent_event_id": "TEXT",
        "branch_origin_event_id": "TEXT",
        "growth_summary": "TEXT",
        "created_at": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in event_cols:
            conn.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")
    conn.execute(
        "UPDATE events SET created_at = updated_at WHERE created_at IS NULL"
    )


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
