"""Pydantic request/response models for ME.xyz MVP API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- Shared ----------

class GateState(BaseModel):
    emotion_stable: bool = False
    info_complete: bool = False
    user_willing: bool = False

    @property
    def ready(self) -> bool:
        return self.emotion_stable and self.info_complete and self.user_willing


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    ts: str = ""


class PersonaPublic(BaseModel):
    id: str
    title: str
    mood: str
    accent: Literal["moss", "slate", "ochre", "plum", "rose"]
    path: str
    day: str
    cost: str


class PersonaFull(PersonaPublic):
    system_prompt: str
    created_at: str = ""


# ---------- Chat ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    gate_state: GateState
    ready_for_personas: bool
    turn_count: int = 0
    phase: str = "contain"


# ---------- Personas ----------

class GeneratePersonasRequest(BaseModel):
    session_id: Optional[str] = None


class GeneratePersonasResponse(BaseModel):
    ready: bool
    gate_state: GateState
    personas: list[PersonaFull] = []


class PersonasListResponse(BaseModel):
    personas: list[PersonaPublic]


# ---------- Role chat ----------

class RoleChatRequest(BaseModel):
    persona_id: str
    message: str = Field(..., min_length=1)


class RoleChatResponse(BaseModel):
    session_id: str
    persona_id: str
    reply: str


class EnsureRoleSessionRequest(BaseModel):
    persona_id: str


class EnsureRoleSessionResponse(BaseModel):
    session_id: str
    persona_id: str
    message_count: int
    created: bool


# ---------- Sessions ----------

class MainSessionSummary(BaseModel):
    session_id: str
    title: str
    message_count: int
    ready_for_personas: bool


class RoleSessionSummary(BaseModel):
    session_id: str
    persona_id: str
    title: str
    accent: str


class SessionsListResponse(BaseModel):
    mains: list[MainSessionSummary]
    roles: list[RoleSessionSummary]


class CreateMainResponse(BaseModel):
    session_id: str
    title: str
    gate_state: GateState


class SessionDetailResponse(BaseModel):
    session_id: str
    type: str
    title: Optional[str] = None
    messages: list[ChatMessage]
    persona_id: Optional[str] = None
    gate_state: Optional[GateState] = None
    turn_count: int = 0
    phase: str = "contain"
    ready_for_personas: bool = False


# ---------- Mindmap ----------

class MindmapNode(BaseModel):
    id: str
    label: str
    kind: str
    source_session: Optional[str] = None
    summary: Optional[str] = None


class MindmapEdge(BaseModel):
    from_: str = Field(..., alias="from")
    to: str

    model_config = {"populate_by_name": True}


class MindmapData(BaseModel):
    nodes: list[MindmapNode] = []
    edges: list[dict] = []


class MindmapExtractRequest(BaseModel):
    session_id: str = "main_1"
    kind_hint: Optional[str] = "decision"


class MindmapExtractResponse(BaseModel):
    nodes_added: list[MindmapNode]
    mindmap: MindmapData


# ---------- Auth ----------

class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    nickname: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    email: str
    nickname: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class EmailCodeRequest(BaseModel):
    email: str = Field(..., min_length=3)


class EmailCodeSendResponse(BaseModel):
    ok: bool = True
    cooldown_seconds: int


class RegisterVerifyRequest(BaseModel):
    email: str = Field(..., min_length=3)
    code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=6)
    nickname: Optional[str] = None


# ---------- Memory ----------

class OrganizeMemoryRequest(BaseModel):
    session_id: str


class OrganizeMemoryResponse(BaseModel):
    session_id: str
    created: list[dict] = []
    merged: list[dict] = []
    discarded: list[dict] = []
    mindmap: MindmapData
