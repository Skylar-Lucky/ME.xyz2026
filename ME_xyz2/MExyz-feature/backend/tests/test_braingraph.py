from datetime import datetime, timezone

import pytest

from braingraph.graph_service import GraphBuilder, GraphValidationError
from braingraph.models import Emotion, EventRecord
from braingraph.repository import CsvMemoryRepository


def _event(event_id: str, parent: str | None = None) -> EventRecord:
    now = datetime.now(timezone.utc)
    return EventRecord(
        event_id=event_id,
        user_id="user-a",
        conversation_id="main_1",
        source_turn_id=f"turn-{event_id}",
        event_time=now,
        event_content=f"事件 {event_id}",
        emotions=[
            Emotion(code="anxiety", label="焦虑", intensity=0.6, score=0.5)
        ],
        viewpoint="我正在理解这件事。",
        branch_id="main",
        parent_event_id=parent,
        created_at=now,
    )


def test_graph_builder_creates_event_emotion_and_viewpoint_nodes():
    graph = GraphBuilder().build([_event("event-1"), _event("event-2", "event-1")])
    assert graph.stats.eventCount == 2
    assert graph.stats.emotionCount == 1
    assert any(link.type == "NEXT_EVENT" for link in graph.links)
    assert sum(node.type == "viewpoint" for node in graph.nodes) == 2


def test_graph_builder_rejects_missing_parent():
    with pytest.raises(GraphValidationError, match="父事件不存在"):
        GraphBuilder().build([_event("event-2", "missing")])


def test_csv_repository_isolates_users(tmp_path):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "event_id,user_id,conversation_id,source_turn_id,event_time,event_content,"
        "emotions_json,viewpoint,branch_id,parent_event_id,branch_origin_event_id,"
        "persona_id,persona_name,created_at\n"
        'event-1,user-a,main_1,turn-1,2026-01-01T00:00:00+00:00,事件一,'
        '"[{""code"":""calm"",""label"":""平静"",""intensity"":0.5,""score"":0.5}]",'
        "观点,main,,,,,2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    repository = CsvMemoryRepository(csv_path)
    assert len(repository.list_events("user-a")) == 1
    assert repository.list_events("user-b") == []

