"""ME.xyz FastAPI — SQLite + auth + memory organize."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import auth
import conversation
import memory_agent
import prompt
import store
from braingraph.api import router as memory_graph_router
from braingraph.exporter import export_memory_events
from db import init_db
from llm_service import LLMError, chat, chat_json
from models import (
    AuthRequest,
    AuthResponse,
    ChangePasswordRequest,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreateMainResponse,
    DeleteAccountRequest,
    EmailCodeRequest,
    EmailCodeSendResponse,
    EnsureRoleSessionRequest,
    EnsureRoleSessionResponse,
    GateState,
    GeneratePersonasRequest,
    GeneratePersonasResponse,
    MainSessionSummary,
    MindmapData,
    MindmapExtractRequest,
    MindmapExtractResponse,
    MindmapNode,
    OkResponse,
    OrganizeMemoryRequest,
    OrganizeMemoryResponse,
    PersonaFull,
    PersonaPublic,
    PersonasListResponse,
    RegisterVerifyRequest,
    RoleChatRequest,
    RoleChatResponse,
    RoleSessionSummary,
    SessionDetailResponse,
    SessionsListResponse,
    UpdateProfileRequest,
    UserPublic,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mexyz.memory")

app = FastAPI(title="ME.xyz MVP API", version="0.3.0")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "ME_xyz"
AVATAR_DIR = Path(__file__).resolve().parent / "data" / "avatars"
app.include_router(memory_graph_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mexyz2026.com", "https://www.mexyz2026.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AVATAR_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/avatars", StaticFiles(directory=AVATAR_DIR), name="avatars")


@app.on_event("startup")
def _startup():
    init_db()
    export_memory_events()


def _gate(d: dict | None) -> GateState:
    d = d or {}
    return GateState(
        emotion_stable=bool(d.get("emotion_stable")),
        info_complete=bool(d.get("info_complete")),
        user_willing=bool(d.get("user_willing")),
    )


def _history_for_llm(messages: list[dict], limit: int = 20) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in messages[-limit:]]


def _resolve_main(user_id: str, session_id: str | None) -> dict:
    main = store.get_main_session(user_id, session_id)
    if not main:
        raise HTTPException(status_code=404, detail="main session not found")
    return main


def _uid(user: dict) -> str:
    return user["id"]


@app.get("/health")
def health():
    return {"ok": True}


# ---------- Auth ----------

@app.post("/api/auth/register", response_model=AuthResponse)
def api_register(body: AuthRequest):
    user = auth.create_user(body.email, body.password, body.nickname)
    store.ensure_user_bootstrap(user["id"])
    token = auth.create_token(user["id"])
    return AuthResponse(
        token=token,
        user=UserPublic(
            id=user["id"], email=user["email"], nickname=user.get("nickname"),
            avatar_url=user.get("avatar_url"),
        ),
    )


@app.post("/api/auth/register/send-code", response_model=EmailCodeSendResponse)
def api_register_send_code(body: EmailCodeRequest):
    cooldown = auth.request_email_code(body.email, purpose="register")
    return EmailCodeSendResponse(cooldown_seconds=cooldown)


@app.post("/api/auth/register/verify-code", response_model=AuthResponse)
def api_register_verify_code(body: RegisterVerifyRequest):
    auth.verify_email_code(body.email, body.code, purpose="register")
    user = auth.create_user(body.email, body.password, body.nickname, email_verified=True)
    store.ensure_user_bootstrap(user["id"])
    token = auth.create_token(user["id"])
    return AuthResponse(
        token=token,
        user=UserPublic(
            id=user["id"], email=user["email"], nickname=user.get("nickname"),
            avatar_url=user.get("avatar_url"),
        ),
    )


@app.post("/api/auth/login", response_model=AuthResponse)
def api_login(body: AuthRequest):
    user = auth.authenticate_user(body.email, body.password)
    store.ensure_user_bootstrap(user["id"])
    token = auth.create_token(user["id"])
    return AuthResponse(
        token=token,
        user=UserPublic(
            id=user["id"], email=user["email"], nickname=user.get("nickname"),
            avatar_url=user.get("avatar_url"),
        ),
    )


@app.get("/api/auth/me", response_model=UserPublic)
def api_me(user: dict = Depends(auth.get_current_user)):
    return UserPublic(
        id=user["id"], email=user["email"], nickname=user.get("nickname"),
        avatar_url=user.get("avatar_url"),
    )


@app.patch("/api/auth/me", response_model=UserPublic)
def api_update_me(body: UpdateProfileRequest, user: dict = Depends(auth.get_current_user)):
    updated = auth.update_nickname(user["id"], body.nickname)
    return UserPublic(
        id=updated["id"], email=updated["email"], nickname=updated.get("nickname"),
        avatar_url=updated.get("avatar_url"),
    )


@app.post("/api/auth/me/avatar", response_model=UserPublic)
async def api_upload_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(auth.get_current_user),
):
    content_type_ext = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }
    ext = content_type_ext.get(file.content_type)
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 PNG / JPG / WEBP 格式的图片")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小需在 5MB 以内")

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    for old in AVATAR_DIR.glob(f"{user['id']}.*"):
        old.unlink(missing_ok=True)
    filename = f"{user['id']}.{ext}"
    (AVATAR_DIR / filename).write_bytes(data)

    avatar_url = f"/uploads/avatars/{filename}?v={int(time.time())}"
    updated = auth.update_avatar(user["id"], avatar_url)
    return UserPublic(
        id=updated["id"], email=updated["email"], nickname=updated.get("nickname"),
        avatar_url=updated.get("avatar_url"),
    )


@app.post("/api/auth/change-password", response_model=OkResponse)
def api_change_password(body: ChangePasswordRequest, user: dict = Depends(auth.get_current_user)):
    auth.change_password(user["id"], body.old_password, body.new_password)
    return OkResponse()


@app.delete("/api/auth/me", response_model=OkResponse)
def api_delete_me(body: DeleteAccountRequest, user: dict = Depends(auth.get_current_user)):
    auth.delete_account(user["id"], body.email)
    return OkResponse()


# ---------- Main chat ----------

@app.post("/api/chat", response_model=ChatResponse)
def api_chat(body: ChatRequest, user: dict = Depends(auth.get_current_user)):
    uid = _uid(user)
    main = _resolve_main(uid, body.session_id)
    sid = main["session_id"]
    store.append_message(uid, sid, "user", body.message)

    turn = store.count_user_turns(uid, sid)
    msgs = store.get_messages(uid, sid)
    prev_state = main.get("conversation_state") or conversation.empty_state()

    # Turn 11+: no guided LLM dialogue; keep button unlocked.
    if conversation.is_chat_closed(turn):
        reply = conversation.CHAT_CLOSED_REPLY
        last_assistant = next(
            (m for m in reversed(msgs) if m.get("role") == "assistant"),
            None,
        )
        if not last_assistant or last_assistant.get("content") != reply:
            store.append_message(uid, sid, "assistant", reply)
        state = prev_state
        phase, _ = conversation.derive_phase(turn, state.get("coverage") or {})
        main["conversation_state"] = state
        main["gate_state"] = conversation.force_ready_gate()
        store.save_main_session(uid, main)
        gate = _gate(main.get("gate_state"))
        return ChatResponse(
            session_id=sid,
            reply=reply,
            gate_state=gate,
            ready_for_personas=True,
            turn_count=turn,
            phase=phase,
        )

    try:
        state = conversation.extract_conversation_state(msgs, prev_state)
    except Exception:
        state = conversation.merge_state(prev_state, {})

    phase, missing = conversation.derive_phase(turn, state.get("coverage") or {})
    system = prompt.build_main_chat_system(turn, phase, state, missing)
    history = _history_for_llm(msgs)

    try:
        reply = chat(history, system=system)
    except LLMError as e:
        store.delete_last_message(uid, sid)
        raise HTTPException(status_code=502, detail=str(e)) from e

    store.append_message(uid, sid, "assistant", reply)
    msgs = store.get_messages(uid, sid)

    # Re-extract after assistant reply for summary/future flags
    try:
        state = conversation.extract_conversation_state(msgs, state)
    except Exception:
        pass

    old_gate = main.get("gate_state") or {}
    new_gate = conversation.gate_from_state(state, turn)
    main["conversation_state"] = state
    # After turn 10, force ready even if earlier gates were incomplete.
    if turn >= conversation.TARGET_TURNS:
        main["gate_state"] = conversation.force_ready_gate()
    else:
        merged = conversation.monotonic_merge(old_gate, new_gate)
        # Hard rule: never unlock willingness before the fixed 10th turn.
        merged["user_willing"] = False
        main["gate_state"] = merged

    store.save_main_session(uid, main)
    gate = _gate(main.get("gate_state"))
    return ChatResponse(
        session_id=sid,
        reply=reply,
        gate_state=gate,
        ready_for_personas=gate.ready,
        turn_count=turn,
        phase=phase,
    )


# ---------- Generate personas ----------

@app.post("/api/generate-personas", response_model=GeneratePersonasResponse)
def api_generate_personas(
    body: GeneratePersonasRequest,
    user: dict = Depends(auth.get_current_user),
):
    uid = _uid(user)
    main = _resolve_main(uid, body.session_id)
    gate = _gate(main.get("gate_state"))

    if not gate.ready:
        return GeneratePersonasResponse(ready=False, gate_state=gate, personas=[])

    msgs = store.get_messages(uid, main["session_id"])
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in msgs[-30:])
    state_json = json.dumps(
        main.get("conversation_state") or conversation.empty_state(),
        ensure_ascii=False,
    )
    try:
        result = chat_json(
            [
                {
                    "role": "user",
                    "content": prompt.PERSONA_GEN_SKILL
                    + "\n\nConversationState 档案：\n"
                    + state_json
                    + "\n\n对话记录：\n"
                    + transcript,
                }
            ],
            temperature=0.7,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    raw_list = result.get("personas") or []
    if len(raw_list) < 3:
        raise HTTPException(status_code=502, detail="模型未返回 3 个角色")

    accents = ["moss", "slate", "ochre", "plum", "rose"]
    used: set[str] = set()
    to_save: list[dict] = []

    for i, raw in enumerate(raw_list[:3]):
        accent = raw.get("accent", accents[i])
        if accent not in accents or accent in used:
            accent = next(a for a in accents if a not in used)
        used.add(accent)
        to_save.append(
            {
                "title": raw.get("title") or f"未来版本 {i + 1}",
                "mood": raw.get("mood") or "",
                "accent": accent,
                "path": raw.get("path") or "",
                "day": raw.get("day") or "",
                "cost": raw.get("cost") or "",
                "system_prompt": raw.get("system_prompt")
                or f"你是用户未来的一个版本：{raw.get('title', '')}。用温和语气与用户对话。",
                "source_session_id": main["session_id"],
            }
        )

    saved = store.upsert_personas(uid, to_save)
    return GeneratePersonasResponse(
        ready=True,
        gate_state=gate,
        personas=[PersonaFull(**s) for s in saved],
    )


@app.get("/api/personas", response_model=PersonasListResponse)
def api_list_personas(user: dict = Depends(auth.get_current_user)):
    all_p = store.get_all_personas(_uid(user))
    items = [
        PersonaPublic(
            id=p["id"],
            title=p["title"],
            mood=p.get("mood", ""),
            accent=p.get("accent", "slate"),
            path=p.get("path", ""),
            day=p.get("day", ""),
            cost=p.get("cost", ""),
        )
        for p in all_p.values()
    ]
    return PersonasListResponse(personas=items)


@app.get("/api/personas/{persona_id}", response_model=PersonaFull)
def api_get_persona(persona_id: str, user: dict = Depends(auth.get_current_user)):
    p = store.get_persona(_uid(user), persona_id)
    if not p:
        raise HTTPException(status_code=404, detail="persona not found")
    return PersonaFull(**{k: v for k, v in p.items() if k != "source_session_id"})


# ---------- Role chat ----------

@app.post("/api/role-chat", response_model=RoleChatResponse)
def api_role_chat(body: RoleChatRequest, user: dict = Depends(auth.get_current_user)):
    uid = _uid(user)
    persona = store.get_persona(uid, body.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="persona not found")

    session = store.ensure_role_session(uid, body.persona_id)
    sid = session["session_id"]
    store.append_message(uid, sid, "user", body.message)

    history = _history_for_llm(store.get_messages(uid, sid))
    system = persona.get("system_prompt") or f"你是「{persona.get('title')}」，用户未来的一个版本。"

    try:
        reply = chat(history, system=system)
    except LLMError as e:
        store.delete_last_message(uid, sid)
        raise HTTPException(status_code=502, detail=str(e)) from e

    store.append_message(uid, sid, "assistant", reply)
    return RoleChatResponse(session_id=sid, persona_id=body.persona_id, reply=reply)


# ---------- Sessions ----------

@app.get("/api/sessions", response_model=SessionsListResponse)
def api_list_sessions(user: dict = Depends(auth.get_current_user)):
    uid = _uid(user)
    personas = store.get_all_personas(uid)

    mains: list[MainSessionSummary] = []
    for m in store.list_mains(uid):
        gate = _gate(m.get("gate_state"))
        mains.append(
            MainSessionSummary(
                session_id=m["session_id"],
                title=m.get("title") or m["session_id"],
                message_count=m.get("message_count") or 0,
                ready_for_personas=gate.ready,
            )
        )

    roles: list[RoleSessionSummary] = []
    for role in store.list_role_sessions(uid):
        pid = role["persona_id"]
        p = personas.get(pid, {})
        roles.append(
            RoleSessionSummary(
                session_id=role["session_id"],
                persona_id=pid,
                title=p.get("title", pid),
                accent=p.get("accent", "slate"),
            )
        )

    return SessionsListResponse(mains=mains, roles=roles)


@app.post("/api/sessions/main", response_model=CreateMainResponse)
def api_create_main(user: dict = Depends(auth.get_current_user)):
    main = store.create_main_session(_uid(user))
    return CreateMainResponse(
        session_id=main["session_id"],
        title=main["title"],
        gate_state=_gate(main.get("gate_state")),
    )


@app.post("/api/sessions/role", response_model=EnsureRoleSessionResponse)
def api_ensure_role(
    body: EnsureRoleSessionRequest,
    user: dict = Depends(auth.get_current_user),
):
    uid = _uid(user)
    persona = store.get_persona(uid, body.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="persona not found")
    existing = store.get_role_session(uid, body.persona_id)
    created = existing is None
    session = store.ensure_role_session(uid, body.persona_id)
    return EnsureRoleSessionResponse(
        session_id=session["session_id"],
        persona_id=body.persona_id,
        message_count=len(session.get("messages") or store.get_messages(uid, session["session_id"])),
        created=created,
    )


@app.get("/api/sessions/{session_id}", response_model=SessionDetailResponse)
def api_get_session(session_id: str, user: dict = Depends(auth.get_current_user)):
    uid = _uid(user)
    session = store.find_session(uid, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    messages = [ChatMessage(**m) for m in session.get("messages", [])]
    gate = _gate(session["gate_state"]) if session.get("gate_state") else None
    turn_count = 0
    phase = "contain"
    ready = False
    if session.get("type") == "main":
        turn_count = store.count_user_turns(uid, session_id)
        state = session.get("conversation_state") or conversation.empty_state()
        phase, _ = conversation.derive_phase(turn_count, state.get("coverage") or {})
        if gate:
            ready = gate.ready
    return SessionDetailResponse(
        session_id=session.get("session_id", session_id),
        type=session.get("type", "main"),
        title=session.get("title"),
        messages=messages,
        persona_id=session.get("persona_id"),
        gate_state=gate,
        turn_count=turn_count,
        phase=phase,
        ready_for_personas=ready,
    )


# ---------- Memory ----------

@app.post("/api/memory/organize", response_model=OrganizeMemoryResponse)
def api_organize_memory(
    body: OrganizeMemoryRequest,
    user: dict = Depends(auth.get_current_user),
):
    uid = _uid(user)
    logger.info("memory.organize start user=%s session=%s", uid, body.session_id)
    if not store.find_session(uid, body.session_id):
        logger.warning("memory.organize session not found user=%s session=%s", uid, body.session_id)
        raise HTTPException(status_code=404, detail="session not found")
    try:
        result = memory_agent.organize_session(uid, body.session_id)
    except ValueError as e:
        logger.warning("memory.organize failed (session gone) user=%s session=%s: %s", uid, body.session_id, e)
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        logger.error("memory.organize LLM error user=%s session=%s: %s", uid, body.session_id, e)
        raise HTTPException(status_code=502, detail=str(e)) from e
    logger.info(
        "memory.organize extracted user=%s session=%s created=%d merged=%d discarded=%d",
        uid, body.session_id, len(result["created"]), len(result["merged"]), len(result["discarded"]),
    )
    try:
        export_memory_events()
    except OSError as e:
        logger.error("memory.organize CSV export failed user=%s session=%s: %s", uid, body.session_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"记忆已保存，但图谱数据同步失败: {e}",
        ) from e
    logger.info("memory.organize CSV synced user=%s session=%s", uid, body.session_id)

    mm = result["mindmap"]
    return OrganizeMemoryResponse(
        session_id=result["session_id"],
        created=result["created"],
        merged=result["merged"],
        discarded=result["discarded"],
        mindmap=MindmapData(
            nodes=[
                MindmapNode(
                    id=n["id"],
                    label=n.get("label") or "",
                    kind=n.get("kind") or "event",
                    source_session=n.get("source_session"),
                    summary=n.get("summary"),
                )
                for n in mm.get("nodes", [])
            ],
            edges=mm.get("edges", []),
        ),
    )


# ---------- Mindmap ----------

@app.get("/api/mindmap", response_model=MindmapData)
def api_get_mindmap(user: dict = Depends(auth.get_current_user)):
    mm = store.get_mindmap(_uid(user))
    return MindmapData(
        nodes=[
            MindmapNode(
                id=n["id"],
                label=n.get("label") or "",
                kind=n.get("kind") or "event",
                source_session=n.get("source_session"),
                summary=n.get("summary"),
            )
            for n in mm.get("nodes", [])
        ],
        edges=mm.get("edges", []),
    )


@app.post("/api/mindmap/extract", response_model=MindmapExtractResponse)
def api_mindmap_extract(
    body: MindmapExtractRequest,
    user: dict = Depends(auth.get_current_user),
):
    """Deprecated placeholder — prefer POST /api/memory/organize."""
    uid = _uid(user)
    session = store.find_session(uid, body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    messages = session.get("messages", [])
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages[-20:])
    kind = body.kind_hint or "decision"
    nodes_added: list[dict] = []

    if transcript.strip():
        try:
            result = chat_json(
                [
                    {
                        "role": "user",
                        "content": prompt.MINDMAP_EXTRACT_PROMPT
                        + transcript
                        + f"\n优先 kind={kind}",
                    }
                ],
                temperature=0.3,
            )
            for raw in (result.get("nodes") or [])[:3]:
                nodes_added.append(
                    {
                        "id": store.new_node_id(),
                        "label": raw.get("label") or "未命名",
                        "kind": raw.get("kind") or kind,
                        "summary": raw.get("summary") or "",
                        "source_session": body.session_id,
                    }
                )
        except LLMError:
            nodes_added = []

    if not nodes_added:
        nodes_added = [
            {
                "id": store.new_node_id(),
                "label": "对话片段",
                "kind": kind,
                "summary": "占位节点：请改用「整理记忆」。",
                "source_session": body.session_id,
            }
        ]

    mm = store.add_mindmap_nodes(uid, nodes_added)
    return MindmapExtractResponse(
        nodes_added=[MindmapNode(**{k: n.get(k) for k in ("id", "label", "kind", "summary", "source_session")}) for n in nodes_added],
        mindmap=MindmapData(
            nodes=[
                MindmapNode(
                    id=n["id"],
                    label=n.get("label") or "",
                    kind=n.get("kind") or "event",
                    source_session=n.get("source_session"),
                    summary=n.get("summary"),
                )
                for n in mm.get("nodes", [])
            ],
            edges=mm.get("edges", []),
        ),
    )


# Serve the SPA and API from one process. API routes are registered first, so
# the static catch-all cannot shadow them.
if FRONTEND_DIR.is_dir():
    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
