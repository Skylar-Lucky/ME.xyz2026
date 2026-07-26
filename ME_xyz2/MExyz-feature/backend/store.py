"""SQLite-backed store for sessions, messages, personas, events, mindmap."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from db import get_connection, init_db

_EMPTY_GATE = {
    "emotion_stable": False,
    "info_complete": False,
    "user_willing": False,
}

_EMPTY_CONVERSATION_STATE: dict = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_loads(raw: str | None) -> dict:
    if not raw:
        return dict(_EMPTY_CONVERSATION_STATE)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else dict(_EMPTY_CONVERSATION_STATE)
    except json.JSONDecodeError:
        return dict(_EMPTY_CONVERSATION_STATE)


def _gate_loads(raw: str | None) -> dict:
    if not raw:
        return dict(_EMPTY_GATE)
    try:
        return {**_EMPTY_GATE, **json.loads(raw)}
    except json.JSONDecodeError:
        return dict(_EMPTY_GATE)


def ensure_user_bootstrap(user_id: str) -> None:
    """Ensure user has main_1 and center mindmap node."""
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM sessions WHERE user_id = ? AND type = 'main' LIMIT 1",
            (user_id,),
        ).fetchone()
        if not row:
            ts = _now()
            conn.execute(
                """INSERT INTO sessions
                   (user_id, id, type, title, persona_id, gate_json, conversation_state_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
                    "main_1",
                    "main",
                    "主对话1",
                    None,
                    json.dumps(_EMPTY_GATE, ensure_ascii=False),
                    json.dumps(_EMPTY_CONVERSATION_STATE, ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
        node = conn.execute(
            "SELECT id FROM mindmap_nodes WHERE user_id = ? AND id = 'self'",
            (user_id,),
        ).fetchone()
        if not node:
            conn.execute(
                """INSERT INTO mindmap_nodes
                   (id, user_id, label, kind, summary, source_session, event_id, world, branch_id)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                ("self", user_id, "你", "center", None, None, None, None, None),
            )
        conn.commit()
    finally:
        conn.close()


# ---------- Sessions ----------

def list_mains(user_id: str) -> list[dict]:
    ensure_user_bootstrap(user_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT s.*,
                      (SELECT COUNT(*) FROM messages m
                       WHERE m.user_id = s.user_id AND m.session_id = s.id) AS message_count
               FROM sessions s
               WHERE s.user_id = ? AND s.type = 'main'
               ORDER BY s.created_at ASC""",
            (user_id,),
        ).fetchall()
        out = []
        for r in rows:
            gate = _gate_loads(r["gate_json"])
            out.append(
                {
                    "session_id": r["id"],
                    "title": r["title"] or r["id"],
                    "type": "main",
                    "gate_state": gate,
                    "message_count": r["message_count"],
                    "messages": [],  # filled on demand
                }
            )
        return out
    finally:
        conn.close()


def create_main_session(user_id: str) -> dict:
    ensure_user_bootstrap(user_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM sessions WHERE user_id = ? AND type = 'main'",
            (user_id,),
        ).fetchall()
        used = {r["id"] for r in rows}
        n = 1
        while f"main_{n}" in used:
            n += 1
        sid = f"main_{n}"
        ts = _now()
        gate = dict(_EMPTY_GATE)
        conn.execute(
            """INSERT INTO sessions
               (user_id, id, type, title, persona_id, gate_json, conversation_state_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                user_id,
                sid,
                "main",
                f"主对话{n}",
                None,
                json.dumps(gate, ensure_ascii=False),
                json.dumps(_EMPTY_CONVERSATION_STATE, ensure_ascii=False),
                ts,
                ts,
            ),
        )
        conn.commit()
        return {
            "session_id": sid,
            "title": f"主对话{n}",
            "type": "main",
            "gate_state": gate,
            "conversation_state": dict(_EMPTY_CONVERSATION_STATE),
            "messages": [],
        }
    finally:
        conn.close()


def get_main_session(user_id: str, session_id: str | None = None) -> dict | None:
    ensure_user_bootstrap(user_id)
    if not session_id:
        mains = list_mains(user_id)
        if not mains:
            return None
        session_id = mains[0]["session_id"]
    return find_session(user_id, session_id)


def save_main_session(user_id: str, main: dict) -> None:
    """Persist gate_state and conversation_state (messages via append_message)."""
    sid = main["session_id"]
    gate = main.get("gate_state") or _EMPTY_GATE
    state = main.get("conversation_state") or _EMPTY_CONVERSATION_STATE
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE sessions SET gate_json = ?, conversation_state_json = ?,
               title = COALESCE(?, title), updated_at = ?
               WHERE user_id = ? AND id = ?""",
            (
                json.dumps(gate, ensure_ascii=False),
                json.dumps(state, ensure_ascii=False),
                main.get("title"),
                _now(),
                user_id,
                sid,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_role_session(user_id: str, persona_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND persona_id = ? AND type = 'role'",
            (user_id, persona_id),
        ).fetchone()
        if not row:
            return None
        return _session_from_row(user_id, row, include_messages=True)
    finally:
        conn.close()


def ensure_role_session(user_id: str, persona_id: str) -> dict:
    existing = get_role_session(user_id, persona_id)
    if existing:
        return existing
    sid = f"role-{persona_id}"
    ts = _now()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO sessions
               (user_id, id, type, title, persona_id, gate_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, sid, "role", None, persona_id, None, ts, ts),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "session_id": sid,
        "type": "role",
        "persona_id": persona_id,
        "messages": [],
    }


def list_role_sessions(user_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND type = 'role' ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [
            {
                "session_id": r["id"],
                "persona_id": r["persona_id"],
                "type": "role",
            }
            for r in rows
        ]
    finally:
        conn.close()


def _session_from_row(user_id: str, row: Any, include_messages: bool = True) -> dict:
    sess = {
        "session_id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "persona_id": row["persona_id"],
        "gate_state": _gate_loads(row["gate_json"]) if row["type"] == "main" else None,
        "conversation_state": _state_loads(row["conversation_state_json"])
        if row["type"] == "main"
        else None,
        "messages": [],
    }
    if include_messages:
        sess["messages"] = get_messages(user_id, row["id"])
    return sess


def find_session(user_id: str, session_id: str) -> dict | None:
    ensure_user_bootstrap(user_id)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND id = ?",
            (user_id, session_id),
        ).fetchone()
        if not row and session_id == "main-demo":
            row = conn.execute(
                "SELECT * FROM sessions WHERE user_id = ? AND type = 'main' ORDER BY created_at LIMIT 1",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return _session_from_row(user_id, row, include_messages=True)
    finally:
        conn.close()


def count_user_turns(user_id: str, session_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM messages
               WHERE user_id = ? AND session_id = ? AND role = 'user'""",
            (user_id, session_id),
        ).fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()


def get_messages(user_id: str, session_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, role, content, ts FROM messages
               WHERE user_id = ? AND session_id = ?
               ORDER BY ts ASC, id ASC""",
            (user_id, session_id),
        ).fetchall()
        return [
            {"id": r["id"], "role": r["role"], "content": r["content"], "ts": r["ts"]}
            for r in rows
        ]
    finally:
        conn.close()


def append_message(user_id: str, session_id: str, role: str, content: str) -> dict:
    msg_id = f"m_{uuid.uuid4().hex[:12]}"
    ts = _now()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO messages (id, session_id, user_id, role, content, ts)
               VALUES (?,?,?,?,?,?)""",
            (msg_id, session_id, user_id, role, content, ts),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE user_id = ? AND id = ?",
            (ts, user_id, session_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": msg_id, "role": role, "content": content, "ts": ts}


def delete_last_message(user_id: str, session_id: str) -> None:
    """Rollback helper after LLM failure."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT id FROM messages WHERE user_id = ? AND session_id = ?
               ORDER BY ts DESC, id DESC LIMIT 1""",
            (user_id, session_id),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM messages WHERE id = ?", (row["id"],))
            conn.commit()
    finally:
        conn.close()


# ---------- Personas ----------

def get_all_personas(user_id: str) -> dict[str, dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM personas WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
        out: dict[str, dict] = {}
        for r in rows:
            out[r["id"]] = {
                "id": r["id"],
                "title": r["title"] or "",
                "mood": r["mood"] or "",
                "accent": r["accent"] or "slate",
                "path": r["path"] or "",
                "day": r["day"] or "",
                "cost": r["cost"] or "",
                "system_prompt": r["system_prompt"] or "",
                "source_session_id": r["source_session_id"],
                "created_at": r["created_at"],
            }
        return out
    finally:
        conn.close()


def get_persona(user_id: str, persona_id: str) -> dict | None:
    return get_all_personas(user_id).get(persona_id)


def upsert_personas(user_id: str, new_list: list[dict]) -> list[dict]:
    conn = get_connection()
    try:
        saved = []
        for p in new_list:
            pid = p.get("id") or f"p_{uuid.uuid4().hex[:8]}"
            created = p.get("created_at") or _now()
            conn.execute(
                """INSERT INTO personas
                   (id, user_id, title, mood, accent, path, day, cost, system_prompt, source_session_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id, id) DO UPDATE SET
                     title=excluded.title, mood=excluded.mood, accent=excluded.accent,
                     path=excluded.path, day=excluded.day, cost=excluded.cost,
                     system_prompt=excluded.system_prompt, source_session_id=excluded.source_session_id""",
                (
                    pid,
                    user_id,
                    p.get("title") or "",
                    p.get("mood") or "",
                    p.get("accent") or "slate",
                    p.get("path") or "",
                    p.get("day") or "",
                    p.get("cost") or "",
                    p.get("system_prompt") or "",
                    p.get("source_session_id"),
                    created,
                ),
            )
            saved.append(
                {
                    "id": pid,
                    "title": p.get("title") or "",
                    "mood": p.get("mood") or "",
                    "accent": p.get("accent") or "slate",
                    "path": p.get("path") or "",
                    "day": p.get("day") or "",
                    "cost": p.get("cost") or "",
                    "system_prompt": p.get("system_prompt") or "",
                    "created_at": created,
                }
            )
        conn.commit()
        return saved
    finally:
        conn.close()


# ---------- Events / Memory ----------

def list_events(user_id: str, world: str | None = None, branch_id: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        if world is None:
            rows = conn.execute(
                "SELECT * FROM events WHERE user_id = ? ORDER BY updated_at ASC",
                (user_id,),
            ).fetchall()
        elif branch_id is None:
            rows = conn.execute(
                """SELECT * FROM events WHERE user_id = ? AND world = ? AND branch_id IS NULL
                   ORDER BY updated_at ASC""",
                (user_id, world),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM events WHERE user_id = ? AND world = ? AND branch_id = ?
                   ORDER BY updated_at ASC""",
                (user_id, world, branch_id),
            ).fetchall()
        return [_event_from_row(r) for r in rows]
    finally:
        conn.close()


def _event_from_row(r: Any) -> dict:
    try:
        emotions = json.loads(r["emotions_json"] or "[]")
    except json.JSONDecodeError:
        emotions = []
    try:
        evidence = json.loads(r["evidence_json"] or "[]")
    except json.JSONDecodeError:
        evidence = []
    try:
        emotion_details = json.loads(r["emotions_detail_json"] or "[]")
    except json.JSONDecodeError:
        emotion_details = []
    return {
        "event_id": r["id"],
        "event_time": r["event_time"] or "时间不明确",
        "event": r["event"] or "",
        "emotions": emotions,
        "emotion_details": emotion_details,
        "viewpoint": r["viewpoint"] or "",
        "world": r["world"],
        "branch_id": r["branch_id"],
        "source_session_id": r["source_session_id"],
        "event_time_iso": r["event_time_iso"],
        "source_turn_id": r["source_turn_id"],
        "parent_event_id": r["parent_event_id"],
        "branch_origin_event_id": r["branch_origin_event_id"],
        "growth_summary": r["growth_summary"] or "",
        "evidence": evidence,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def upsert_event(user_id: str, event: dict) -> dict:
    eid = event.get("event_id") or f"event_{uuid.uuid4().hex[:10]}"
    ts = _now()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO events
               (id, user_id, event_time, event, emotions_json, viewpoint, world, branch_id,
                source_session_id, evidence_json, event_time_iso, emotions_detail_json,
                source_turn_id, parent_event_id, branch_origin_event_id, growth_summary, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 user_id=excluded.user_id,
                 event_time=excluded.event_time,
                 event=excluded.event,
                 emotions_json=excluded.emotions_json,
                 viewpoint=excluded.viewpoint,
                 world=excluded.world,
                 branch_id=excluded.branch_id,
                 source_session_id=excluded.source_session_id,
                 evidence_json=excluded.evidence_json,
                 event_time_iso=excluded.event_time_iso,
                 emotions_detail_json=excluded.emotions_detail_json,
                 source_turn_id=excluded.source_turn_id,
                 parent_event_id=excluded.parent_event_id,
                 branch_origin_event_id=excluded.branch_origin_event_id,
                 growth_summary=excluded.growth_summary,
                 created_at=COALESCE(events.created_at, excluded.created_at),
                 updated_at=excluded.updated_at""",
            (
                eid,
                user_id,
                event.get("event_time") or "时间不明确",
                event.get("event") or "",
                json.dumps(event.get("emotions") or [], ensure_ascii=False),
                event.get("viewpoint") or "",
                event.get("world") or "real",
                event.get("branch_id"),
                event.get("source_session_id"),
                json.dumps(event.get("evidence") or [], ensure_ascii=False),
                event.get("event_time_iso"),
                json.dumps(event.get("emotion_details") or [], ensure_ascii=False),
                event.get("source_turn_id"),
                event.get("parent_event_id"),
                event.get("branch_origin_event_id"),
                event.get("growth_summary") or "",
                event.get("created_at") or ts,
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    event["event_id"] = eid
    event.setdefault("created_at", ts)
    event["updated_at"] = ts
    return event


def project_event_to_mindmap(user_id: str, event: dict) -> None:
    """Upsert mindmap node for an event and edge from self."""
    ensure_user_bootstrap(user_id)
    eid = event["event_id"]
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO mindmap_nodes
               (id, user_id, label, kind, summary, source_session, event_id, world, branch_id)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id, id) DO UPDATE SET
                 label=excluded.label, summary=excluded.summary,
                 source_session=excluded.source_session, world=excluded.world,
                 branch_id=excluded.branch_id""",
            (
                eid,
                user_id,
                event.get("event") or "事件",
                "event",
                event.get("viewpoint") or "",
                event.get("source_session_id"),
                eid,
                event.get("world"),
                event.get("branch_id"),
            ),
        )
        edge = conn.execute(
            """SELECT id FROM mindmap_edges
               WHERE user_id = ? AND from_id = 'self' AND to_id = ?""",
            (user_id, eid),
        ).fetchone()
        if not edge:
            conn.execute(
                "INSERT INTO mindmap_edges (user_id, from_id, to_id) VALUES (?,?,?)",
                (user_id, "self", eid),
            )
        conn.commit()
    finally:
        conn.close()


# ---------- Mindmap ----------

def get_mindmap(user_id: str) -> dict:
    ensure_user_bootstrap(user_id)
    conn = get_connection()
    try:
        nodes = conn.execute(
            "SELECT * FROM mindmap_nodes WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        edges = conn.execute(
            "SELECT from_id, to_id FROM mindmap_edges WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {
            "nodes": [
                {
                    "id": n["id"],
                    "label": n["label"] or "",
                    "kind": n["kind"] or "event",
                    "summary": n["summary"],
                    "source_session": n["source_session"],
                    "event_id": n["event_id"],
                    "world": n["world"],
                    "branch_id": n["branch_id"],
                }
                for n in nodes
            ],
            "edges": [{"from": e["from_id"], "to": e["to_id"]} for e in edges],
        }
    finally:
        conn.close()


def add_mindmap_nodes(user_id: str, nodes: list[dict]) -> dict:
    ensure_user_bootstrap(user_id)
    conn = get_connection()
    try:
        for n in nodes:
            nid = n.get("id") or new_node_id()
            conn.execute(
                """INSERT INTO mindmap_nodes
                   (id, user_id, label, kind, summary, source_session, event_id, world, branch_id)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id, id) DO NOTHING""",
                (
                    nid,
                    user_id,
                    n.get("label") or "",
                    n.get("kind") or "event",
                    n.get("summary"),
                    n.get("source_session"),
                    n.get("event_id"),
                    n.get("world"),
                    n.get("branch_id"),
                ),
            )
            if n.get("kind") != "center":
                edge = conn.execute(
                    """SELECT id FROM mindmap_edges
                       WHERE user_id = ? AND from_id = 'self' AND to_id = ?""",
                    (user_id, nid),
                ).fetchone()
                if not edge:
                    conn.execute(
                        "INSERT INTO mindmap_edges (user_id, from_id, to_id) VALUES (?,?,?)",
                        (user_id, "self", nid),
                    )
        conn.commit()
    finally:
        conn.close()
    return get_mindmap(user_id)


def new_node_id() -> str:
    return f"n_{uuid.uuid4().hex[:8]}"


def gates_ready(gate_state: dict) -> bool:
    return bool(
        gate_state.get("emotion_stable")
        and gate_state.get("info_complete")
        and gate_state.get("user_willing")
    )


def new_event_id() -> str:
    return f"event_{uuid.uuid4().hex[:10]}"
