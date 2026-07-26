from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

import auth

from .config import settings
from .graph_service import GraphBuilder, GraphValidationError, filter_events
from .models import EventDetail, GraphResponse
from .repository import CsvMemoryRepository

router = APIRouter(prefix="/api", tags=["memory-graph"])


def _repository() -> CsvMemoryRepository:
    return CsvMemoryRepository(settings.csv_path)


@router.get("/memory-graph", response_model=GraphResponse)
def get_memory_graph(
    branch_id: str | None = None,
    emotion_code: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    search: str | None = None,
    limit: int = Query(300, ge=1, le=500),
    user: dict = Depends(auth.get_current_user),
    repository: CsvMemoryRepository = Depends(_repository),
):
    try:
        events = repository.list_events(user["id"])
        selected = filter_events(
            events,
            branch_id,
            emotion_code,
            start_time,
            end_time,
            search,
            limit,
        )
        return GraphBuilder().build(selected)
    except (ValueError, GraphValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memory-events/{event_id}", response_model=EventDetail)
def get_memory_event(
    event_id: str,
    user: dict = Depends(auth.get_current_user),
    repository: CsvMemoryRepository = Depends(_repository),
):
    events = repository.list_events(user["id"])
    event = next((item for item in events if item.event_id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    children = [item.event_id for item in events if item.parent_event_id == event_id]
    return EventDetail(**event.model_dump(), children=children)

