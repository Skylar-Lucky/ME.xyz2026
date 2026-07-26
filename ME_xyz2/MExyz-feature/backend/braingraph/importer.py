from __future__ import annotations

import csv
import json
from pathlib import Path

import store
from db import get_connection

from .exporter import export_memory_events
from .models import EventRecord


def _ensure_sessions_and_personas(
    user_id: str, records: list[EventRecord]
) -> None:
    """Create the source sessions/personas needed for imported graph records."""
    main_conversation = next(
        (record.conversation_id for record in records if record.branch_id == "main"),
        "conv_main",
    )
    personas = {
        record.persona_id: record
        for record in records
        if record.persona_id and record.persona_name
    }
    if personas:
        store.upsert_personas(
            user_id,
            [
                {
                    "id": persona_id,
                    "title": record.persona_name,
                    "mood": "模拟记忆分支",
                    "accent": accent,
                    "path": "",
                    "day": "",
                    "cost": "",
                    "system_prompt": f"你是用户未来的一个版本：{record.persona_name}。",
                    "source_session_id": main_conversation,
                }
                for (persona_id, record), accent in zip(
                    personas.items(), ["moss", "slate", "ochre", "plum", "rose"]
                )
            ],
        )

    conn = get_connection()
    try:
        conversations: dict[str, tuple[str, str | None]] = {}
        for record in records:
            session_type = "main" if record.branch_id == "main" else "role"
            conversations[record.conversation_id] = (
                session_type,
                record.persona_id,
            )
        for conversation_id, (session_type, persona_id) in conversations.items():
            first = next(
                record
                for record in records
                if record.conversation_id == conversation_id
            )
            conn.execute(
                """INSERT INTO sessions
                   (user_id, id, type, title, persona_id, gate_json,
                    conversation_state_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id, id) DO UPDATE SET
                     title=excluded.title, persona_id=excluded.persona_id,
                     updated_at=excluded.updated_at""",
                (
                    user_id,
                    conversation_id,
                    session_type,
                    first.persona_name or "模拟主对话",
                    persona_id,
                    "{}" if session_type == "main" else None,
                    "{}" if session_type == "main" else None,
                    first.created_at.isoformat(),
                    first.created_at.isoformat(),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def import_graph_csv(source: Path, user_id: str) -> int:
    """Import Braingraph fixtures into canonical SQLite, then rebuild projection."""
    with source.open(encoding="utf-8-sig", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    records = [
        EventRecord(
            **{
                **row,
                "user_id": user_id,
                "emotions": json.loads(row.pop("emotions_json")),
            }
        )
        for row in raw_rows
    ]
    _ensure_sessions_and_personas(user_id, records)

    for record in records:
        existing = store.list_events(user_id)
        conflicting = next(
            (
                event
                for event in existing
                if event["event_id"] == record.event_id
            ),
            None,
        )
        payload = {
            "event_id": record.event_id,
            "event_time": record.event_time.date().isoformat(),
            "event_time_iso": record.event_time.isoformat(),
            "event": record.event_content,
            "emotions": [emotion.label for emotion in record.emotions],
            "emotion_details": [
                emotion.model_dump() for emotion in record.emotions
            ],
            "viewpoint": record.viewpoint,
            "world": "real" if record.branch_id == "main" else "future",
            "branch_id": None if record.branch_id == "main" else record.branch_id,
            "source_session_id": record.conversation_id,
            "source_turn_id": record.source_turn_id,
            "parent_event_id": record.parent_event_id,
            "branch_origin_event_id": record.branch_origin_event_id,
            "growth_summary": record.growth_summary,
            "evidence": [],
            "created_at": record.created_at.isoformat(),
        }
        if conflicting:
            payload["created_at"] = conflicting.get("created_at") or payload["created_at"]
        saved = store.upsert_event(user_id, payload)
        store.project_event_to_mindmap(user_id, saved)

    export_memory_events()
    return len(records)
