from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db import get_connection

from .config import settings
from .models import EMOTION_ALIASES, EMOTIONS, Emotion, EventRecord
from .repository import CSV_FIELDS


def _datetime(value: str | None, fallback: str | None = None) -> datetime:
    candidate = value or fallback
    if candidate:
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _emotion_details(row: Any) -> list[Emotion]:
    try:
        raw_details = json.loads(row["emotions_detail_json"] or "[]")
    except (json.JSONDecodeError, TypeError):
        raw_details = []
    if raw_details:
        return [Emotion.model_validate(item) for item in raw_details[:2]]
    try:
        raw_labels = json.loads(row["emotions_json"] or "[]")
    except (json.JSONDecodeError, TypeError):
        raw_labels = []
    details: list[Emotion] = []
    for raw in raw_labels[:2]:
        if isinstance(raw, dict):
            details.append(Emotion.model_validate(raw))
            continue
        label = str(raw or "迷茫")
        code = EMOTION_ALIASES.get(label, label.lower())
        if code not in EMOTIONS:
            code = "confusion"
        details.append(
            Emotion(code=code, label=EMOTIONS[code], intensity=0.5, score=0.5)
        )
    return details


def build_event_records() -> list[EventRecord]:
    """Map the complete SQLite event projection to graph-domain records."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT e.*, s.persona_id, p.title AS persona_name,
                      p.source_session_id AS persona_source_session_id
               FROM events e
               LEFT JOIN sessions s
                 ON s.user_id = e.user_id AND s.id = e.source_session_id
               LEFT JOIN personas p
                 ON p.user_id = e.user_id AND p.id = s.persona_id
               ORDER BY e.user_id,
                        COALESCE(e.event_time_iso, e.created_at, e.updated_at),
                        e.id"""
        ).fetchall()
    finally:
        conn.close()

    previous_by_branch: dict[tuple[str, str], str] = {}
    latest_real_by_user: dict[str, str] = {}
    latest_real_by_session: dict[tuple[str, str], str] = {}
    records: list[EventRecord] = []
    for row in rows:
        user_id = row["user_id"]
        is_future = row["world"] == "future"
        branch_id = (row["branch_id"] or row["persona_id"]) if is_future else "main"
        branch_id = branch_id or "main"
        parent_id = row["parent_event_id"]
        origin_id = row["branch_origin_event_id"]
        if is_future:
            if not origin_id:
                source_main = row["persona_source_session_id"]
                origin_id = (
                    latest_real_by_session.get((user_id, source_main))
                    if source_main
                    else None
                ) or latest_real_by_user.get(user_id)
            parent_id = parent_id or previous_by_branch.get((user_id, branch_id)) or origin_id
        else:
            parent_id = parent_id or previous_by_branch.get((user_id, "main"))

        updated_at = _datetime(row["updated_at"])
        record = EventRecord(
            event_id=row["id"],
            user_id=user_id,
            conversation_id=row["source_session_id"] or "",
            source_turn_id=row["source_turn_id"] or row["id"],
            event_time=_datetime(row["event_time_iso"], row["updated_at"]),
            event_content=row["event"] or "",
            emotions=_emotion_details(row),
            viewpoint=row["viewpoint"] or "",
            branch_id=branch_id,
            parent_event_id=parent_id,
            branch_origin_event_id=origin_id,
            persona_id=row["persona_id"] if is_future else None,
            persona_name=row["persona_name"] if is_future else None,
            growth_summary=row["growth_summary"] or "",
            created_at=_datetime(row["created_at"], updated_at.isoformat()),
        )
        records.append(record)
        previous_by_branch[(user_id, branch_id)] = record.event_id
        if not is_future:
            latest_real_by_user[user_id] = record.event_id
            latest_real_by_session[(user_id, record.conversation_id)] = record.event_id
    return records


def export_memory_events(path: Path | None = None) -> Path:
    """Atomically rebuild the graph CSV from the canonical SQLite store."""
    destination = path or settings.csv_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    records = build_event_records()
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for record in records:
                row = record.model_dump(mode="json")
                row["emotions_json"] = json.dumps(
                    row.pop("emotions"), ensure_ascii=False
                )
                writer.writerow(row)
        os.replace(temp_path, destination)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
    return destination
