"""Memory Agent: extract events from a finished session and merge into store."""
from __future__ import annotations

import json
from typing import Any

import prompt
import store
from braingraph.models import EMOTION_ALIASES, EMOTIONS, Emotion
from llm_service import LLMError, chat_json


def _norm(s: str) -> str:
    return "".join((s or "").lower().split())


def _find_similar(existing: list[dict], candidate: dict) -> dict | None:
    """Heuristic: same-ish event text; prefer exact/substring match."""
    ce = _norm(candidate.get("event") or "")
    if not ce:
        return None
    best = None
    for ex in existing:
        ee = _norm(ex.get("event") or "")
        if not ee:
            continue
        if ce == ee or ce in ee or ee in ce:
            return ex
        # soft: share many chars
        overlap = len(set(ce) & set(ee))
        if overlap >= max(3, min(len(ce), len(ee)) // 2):
            best = ex
    return best


def _normalize_emotions(raw_items: list) -> tuple[list[str], list[dict]]:
    details: list[Emotion] = []
    for raw in raw_items[:2]:
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
    return [item.label for item in details], [item.model_dump() for item in details]


def _relationship(
    user_id: str,
    world: str,
    branch_id: str | None,
    existing: list[dict],
) -> tuple[str | None, str | None]:
    if world == "real":
        return (existing[-1]["event_id"] if existing else None, None)
    previous = existing[-1]["event_id"] if existing else None
    persona = store.get_persona(user_id, branch_id or "") or {}
    source_main = persona.get("source_session_id")
    real_events = store.list_events(user_id, world="real", branch_id=None)
    scoped = [
        event
        for event in real_events
        if not source_main or event.get("source_session_id") == source_main
    ]
    origin = (scoped or real_events)[-1]["event_id"] if (scoped or real_events) else None
    return previous or origin, origin


def organize_session(user_id: str, session_id: str) -> dict[str, Any]:
    session = store.find_session(user_id, session_id)
    if not session:
        raise ValueError("session not found")

    messages = session.get("messages") or []
    if not messages:
        return {
            "session_id": session_id,
            "created": [],
            "merged": [],
            "discarded": [],
            "mindmap": store.get_mindmap(user_id),
        }

    if session.get("type") == "role":
        world = "future"
        branch_id = session.get("persona_id")
    else:
        world = "real"
        branch_id = None

    existing = store.list_events(user_id, world=world, branch_id=branch_id)
    branch_history = [
        {
            "event_id": event.get("event_id"),
            "event_time": event.get("event_time"),
            "event_time_iso": event.get("event_time_iso"),
            "event": event.get("event"),
            "emotions": event.get("emotion_details") or event.get("emotions") or [],
            "viewpoint": event.get("viewpoint") or "",
            "growth_summary": event.get("growth_summary") or "",
        }
        for event in existing
    ]
    transcript = "\n".join(
        f"[message_id={m['id']}] {m['role']}: {m['content']}" for m in messages
    )
    valid_user_turn_ids = {m["id"] for m in messages if m["role"] == "user"}
    fallback_turn_id = next(
        (m["id"] for m in reversed(messages) if m["role"] == "user"),
        messages[-1]["id"],
    )
    try:
        extracted = chat_json(
            [
                {
                    "role": "user",
                    "content": prompt.MEMORY_EXTRACT_PROMPT
                    + f"world={world}, branch_id={branch_id}\n\n"
                    + "分支历史（已按时间排列；为空表示这是该分支首个事件）：\n"
                    + json.dumps(branch_history, ensure_ascii=False)
                    + "\n\n对话：\n"
                    + transcript,
                }
            ],
            temperature=0.3,
        )
    except LLMError as e:
        raise RuntimeError(str(e)) from e

    candidates = extracted.get("candidate_events") or []
    created: list[dict] = []
    merged: list[dict] = []
    discarded: list[dict] = []

    for cand in candidates:
        event_text = (cand.get("event") or "").strip()
        if not event_text:
            discarded.append({"reason": "empty event", "candidate": cand})
            continue

        emotions, emotion_details = _normalize_emotions(cand.get("emotions") or [])
        growth_summary = str(cand.get("growth_summary") or "").replace("*", "").strip()
        parent_event_id, branch_origin_event_id = _relationship(
            user_id, world, branch_id, existing
        )
        source_turn_id = cand.get("source_turn_id")
        if source_turn_id not in valid_user_turn_ids:
            source_turn_id = fallback_turn_id
        candidate = {
            "event_time": cand.get("event_time") or "时间不明确",
            "event_time_iso": cand.get("event_time_iso"),
            "event": event_text[:20],
            "emotions": emotions,
            "emotion_details": emotion_details,
            "viewpoint": cand.get("viewpoint") or "",
            "growth_summary": growth_summary,
            "evidence": cand.get("evidence") or [],
            "world": world,
            "branch_id": branch_id,
            "source_session_id": session_id,
            "source_turn_id": source_turn_id,
            "parent_event_id": parent_event_id,
            "branch_origin_event_id": branch_origin_event_id,
        }

        similar = _find_similar(existing, candidate)
        action = "create"
        merge_into = None
        emotions = candidate["emotions"]
        emotion_details = candidate["emotion_details"]
        viewpoint = candidate["viewpoint"]
        growth_summary = candidate["growth_summary"]

        if similar:
            try:
                decision = chat_json(
                    [
                        {
                            "role": "user",
                            "content": prompt.MEMORY_MERGE_PROMPT
                            + "\n\n候选事件：\n"
                            + json.dumps(candidate, ensure_ascii=False)
                            + "\n\n已有事件（重点比较这一条）：\n"
                            + json.dumps(similar, ensure_ascii=False),
                        }
                    ],
                    temperature=0.2,
                )
                action = decision.get("action") or "create"
                merge_into = decision.get("merge_into") or similar.get("event_id")
                if decision.get("emotions"):
                    emotions, emotion_details = _normalize_emotions(
                        decision["emotions"]
                    )
                if decision.get("viewpoint"):
                    viewpoint = decision["viewpoint"]
                if action == "discard":
                    discarded.append(
                        {
                            "candidate_event": candidate["event"],
                            "duplicate_of": decision.get("duplicate_of") or similar.get("event_id"),
                            "reason": decision.get("reason") or "no new information",
                        }
                    )
                    continue
            except LLMError:
                # fallback: merge emotions into similar
                action = "merge"
                merge_into = similar["event_id"]
                emotions = list(dict.fromkeys((similar.get("emotions") or []) + candidate["emotions"]))[:2]
                _, emotion_details = _normalize_emotions(emotions)
                viewpoint = candidate["viewpoint"] or similar.get("viewpoint") or ""

        if action == "merge" and merge_into:
            base = next((e for e in existing if e["event_id"] == merge_into), similar)
            if not base:
                action = "create"
            else:
                merged_emotions = list(
                    dict.fromkeys((base.get("emotions") or []) + (emotions or []))
                )[:2]
                updated = store.upsert_event(
                    user_id,
                    {
                        "event_id": base["event_id"],
                        "event_time": candidate["event_time"] or base.get("event_time"),
                        "event": base.get("event") or candidate["event"],
                        "emotions": merged_emotions,
                        "emotion_details": emotion_details,
                        "viewpoint": viewpoint or base.get("viewpoint") or "",
                        "growth_summary": growth_summary
                        or base.get("growth_summary")
                        or "",
                        "world": world,
                        "branch_id": branch_id,
                        "source_session_id": session_id,
                        "event_time_iso": candidate["event_time_iso"]
                        or base.get("event_time_iso"),
                        "source_turn_id": candidate["source_turn_id"]
                        or base.get("source_turn_id"),
                        "parent_event_id": base.get("parent_event_id"),
                        "branch_origin_event_id": base.get("branch_origin_event_id"),
                        "created_at": base.get("created_at"),
                        "evidence": list(
                            dict.fromkeys((base.get("evidence") or []) + (candidate.get("evidence") or []))
                        )[:5],
                    },
                )
                store.project_event_to_mindmap(user_id, updated)
                # refresh existing list
                existing = [updated if e["event_id"] == updated["event_id"] else e for e in existing]
                if not any(e["event_id"] == updated["event_id"] for e in existing):
                    existing.append(updated)
                merged.append(updated)
                continue

        # create
        new_ev = store.upsert_event(
            user_id,
            {
                "event_id": store.new_event_id(),
                **candidate,
                "emotions": emotions,
                "emotion_details": emotion_details,
                "viewpoint": viewpoint,
                "growth_summary": growth_summary,
            },
        )
        store.project_event_to_mindmap(user_id, new_ev)
        existing.append(new_ev)
        created.append(new_ev)

    return {
        "session_id": session_id,
        "created": created,
        "merged": merged,
        "discarded": discarded,
        "mindmap": store.get_mindmap(user_id),
    }
