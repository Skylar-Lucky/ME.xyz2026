from __future__ import annotations

from collections import Counter
from datetime import datetime

from .models import (
    EMOTIONS,
    EventRecord,
    GraphLink,
    GraphNode,
    GraphResponse,
    GraphStats,
)


class GraphValidationError(ValueError):
    pass


class GraphBuilder:
    def validate(self, events: list[EventRecord]) -> None:
        ids = [event.event_id for event in events]
        duplicates = [event_id for event_id, count in Counter(ids).items() if count > 1]
        if duplicates:
            raise GraphValidationError(f"重复事件 ID: {', '.join(duplicates)}")
        known = set(ids)
        for event in events:
            if event.parent_event_id and event.parent_event_id not in known:
                raise GraphValidationError(
                    f"{event.event_id} 的父事件不存在: {event.parent_event_id}"
                )
            invalid = [emotion.code for emotion in event.emotions if emotion.code not in EMOTIONS]
            if invalid:
                raise GraphValidationError(f"{event.event_id} 包含非法情绪: {invalid}")
        parents = {event.event_id: event.parent_event_id for event in events}
        for event_id in ids:
            seen: set[str] = set()
            cursor: str | None = event_id
            while cursor:
                if cursor in seen:
                    raise GraphValidationError(f"检测到事件循环: {event_id}")
                seen.add(cursor)
                cursor = parents.get(cursor)

    def build(self, events: list[EventRecord], version: int = 1) -> GraphResponse:
        self.validate(events)
        by_id = {event.event_id: event for event in events}
        depth_cache: dict[str, int] = {}

        def depth(event: EventRecord) -> int:
            if event.event_id in depth_cache:
                return depth_cache[event.event_id]
            value = depth(by_id[event.parent_event_id]) + 1 if event.parent_event_id else 1
            depth_cache[event.event_id] = value
            return value

        nodes = [GraphNode(id="self", type="self", label="我", depth=0)]
        links: list[GraphLink] = []
        branch_first: dict[str, EventRecord] = {}
        for event in events:
            nodes.append(
                GraphNode(
                    id=event.event_id,
                    type="event",
                    label=event.event_content[:16],
                    depth=depth(event),
                    content=event.event_content,
                    eventTime=event.event_time.isoformat(),
                    viewpoint=event.viewpoint,
                    branchId=event.branch_id,
                    parentEventId=event.parent_event_id,
                    conversationId=event.conversation_id,
                    sourceTurnId=event.source_turn_id,
                    personaName=event.persona_name,
                    emotions=[emotion.model_dump() for emotion in event.emotions],
                )
            )
            branch_first.setdefault(event.branch_id, event)
            if event.parent_event_id and (
                event.branch_id == "main"
                or event.parent_event_id != event.branch_origin_event_id
            ):
                links.append(self._link(event.parent_event_id, event.event_id, "NEXT_EVENT"))
            viewpoint_id = f"viewpoint:{event.event_id}"
            nodes.append(
                GraphNode(
                    id=viewpoint_id,
                    type="viewpoint",
                    label="观点",
                    depth=depth(event),
                    content=event.viewpoint,
                    eventId=event.event_id,
                    branchId=event.branch_id,
                )
            )
            links.append(self._link(event.event_id, viewpoint_id, "HAS_VIEWPOINT", 0.35))

        for branch_id, first in branch_first.items():
            anchor = f"branch:{branch_id}"
            label = "主线记忆" if branch_id == "main" else (first.persona_name or branch_id)
            nodes.append(
                GraphNode(
                    id=anchor,
                    type="branch_anchor",
                    label=label,
                    depth=1,
                    branchId=branch_id,
                    personaId=first.persona_id,
                )
            )
            links.extend(
                [
                    self._link("self", anchor, "BRANCH_FROM"),
                    self._link(anchor, first.event_id, "BRANCH_START"),
                ]
            )

        emotion_counts = Counter(
            emotion.code for event in events for emotion in event.emotions
        )
        for code, count in emotion_counts.items():
            nodes.append(
                GraphNode(
                    id=f"emotion:{code}",
                    type="emotion",
                    label=EMOTIONS[code],
                    depth=max(depth_cache.values(), default=1) + 1,
                    count=count,
                    emotionCode=code,
                )
            )
        for event in events:
            for emotion in event.emotions:
                links.append(
                    self._link(
                        event.event_id,
                        f"emotion:{emotion.code}",
                        "HAS_EMOTION",
                        emotion.intensity,
                    )
                )
        return GraphResponse(
            version=version,
            nodes=nodes,
            links=links,
            stats=GraphStats(
                eventCount=len(events),
                branchCount=len(branch_first),
                emotionCount=len(emotion_counts),
                viewpointCount=len(events),
            ),
        )

    @staticmethod
    def _link(source: str, target: str, kind: str, weight: float = 1) -> GraphLink:
        return GraphLink(
            id=f"{source}->{target}:{kind}",
            source=source,
            target=target,
            type=kind,
            weight=weight,
        )


def filter_events(
    events: list[EventRecord],
    branch_id: str | None = None,
    emotion_code: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    search: str | None = None,
    limit: int = 300,
) -> list[EventRecord]:
    selected = events
    if branch_id:
        selected = [event for event in selected if event.branch_id == branch_id]
    if emotion_code:
        selected = [
            event
            for event in selected
            if any(emotion.code == emotion_code for emotion in event.emotions)
        ]
    if start_time:
        selected = [event for event in selected if event.event_time >= start_time]
    if end_time:
        selected = [event for event in selected if event.event_time <= end_time]
    if search:
        query = search.casefold()
        selected = [
            event
            for event in selected
            if query in f"{event.event_content} {event.viewpoint}".casefold()
            or any(
                query in f"{emotion.code} {emotion.label}".casefold()
                for emotion in event.emotions
            )
        ]
    chosen = selected[:limit]
    all_by_id = {event.event_id: event for event in events}
    result = {event.event_id: event for event in chosen}
    for event in chosen:
        cursor = event
        visited: set[str] = {event.event_id}
        while cursor.parent_event_id and cursor.parent_event_id in all_by_id:
            if cursor.parent_event_id in visited:
                break  # corrupt/cyclic parent chain — stop walking instead of spinning forever
            cursor = all_by_id[cursor.parent_event_id]
            visited.add(cursor.event_id)
            result[cursor.event_id] = cursor
    return sorted(result.values(), key=lambda event: (event.event_time, event.event_id))

