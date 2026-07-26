from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMOTIONS = {
    "joy": "喜悦",
    "optimism": "乐观",
    "satisfaction": "满足",
    "calm": "平静",
    "surprise": "惊讶",
    "confusion": "迷茫",
    "anxiety": "焦虑",
    "sadness": "悲伤",
    "anger": "愤怒",
}
EMOTION_ALIASES = {label: code for code, label in EMOTIONS.items()}


class Emotion(BaseModel):
    code: str
    label: str
    intensity: float = Field(default=0.5, ge=0, le=1)
    score: float = Field(default=0.5, ge=0, le=1)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        return text if text in EMOTIONS else EMOTION_ALIASES.get(text, "confusion")

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: object, info) -> str:
        code = (info.data or {}).get("code", "confusion")
        return EMOTIONS.get(code, str(value or "") or "迷茫")


class MemoryEvent(BaseModel):
    """Canonical writable event shared by Memory Agent, store and exporter."""

    event_id: str = ""
    user_id: str
    event_time: str = "时间不明确"
    event_time_iso: datetime | None = None
    event: str
    emotions: list[str] = Field(default_factory=list, max_length=2)
    emotion_details: list[Emotion] = Field(default_factory=list, max_length=2)
    viewpoint: str = ""
    world: Literal["real", "future"] = "real"
    branch_id: str | None = None
    source_session_id: str
    source_turn_id: str | None = None
    parent_event_id: str | None = None
    branch_origin_event_id: str | None = None
    growth_summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EventRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    event_id: str
    user_id: str
    conversation_id: str
    source_turn_id: str
    event_time: datetime
    event_content: str
    emotions: list[Emotion] = Field(default_factory=list, max_length=2)
    viewpoint: str
    branch_id: str
    parent_event_id: str | None = None
    branch_origin_event_id: str | None = None
    persona_id: str | None = None
    persona_name: str | None = None
    growth_summary: str = ""
    created_at: datetime


class EventDetail(EventRecord):
    children: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    type: Literal["self", "event", "branch_anchor", "emotion", "viewpoint"]
    label: str
    depth: int = 0


class GraphLink(BaseModel):
    id: str
    source: str
    target: str
    type: Literal[
        "SELF_START",
        "NEXT_EVENT",
        "BRANCH_FROM",
        "BRANCH_START",
        "HAS_EMOTION",
        "HAS_VIEWPOINT",
    ]
    weight: float = 1


class GraphStats(BaseModel):
    eventCount: int
    branchCount: int
    emotionCount: int
    viewpointCount: int


class GraphResponse(BaseModel):
    version: int
    nodes: list[GraphNode]
    links: list[GraphLink]
    stats: GraphStats
