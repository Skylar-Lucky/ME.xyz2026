from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol

from .models import EventRecord

CSV_FIELDS = [
    "event_id",
    "user_id",
    "conversation_id",
    "source_turn_id",
    "event_time",
    "event_content",
    "emotions_json",
    "viewpoint",
    "branch_id",
    "parent_event_id",
    "branch_origin_event_id",
    "persona_id",
    "persona_name",
    "growth_summary",
    "created_at",
]


class MemoryRepository(Protocol):
    def list_events(self, user_id: str) -> list[EventRecord]: ...
    def get_event(self, event_id: str, user_id: str) -> EventRecord | None: ...


class CsvMemoryRepository:
    def __init__(self, path: Path):
        self.path = path

    def list_events(self, user_id: str) -> list[EventRecord]:
        if not self.path.exists():
            return []
        records: list[EventRecord] = []
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), 2):
                try:
                    emotions = json.loads(row.pop("emotions_json"))
                    event = EventRecord(**{**row, "emotions": emotions})
                except Exception as exc:
                    raise ValueError(f"CSV 第 {row_number} 行无效: {exc}") from exc
                if event.user_id == user_id:
                    records.append(event)
        return records

    def get_event(self, event_id: str, user_id: str) -> EventRecord | None:
        return next(
            (event for event in self.list_events(user_id) if event.event_id == event_id),
            None,
        )
