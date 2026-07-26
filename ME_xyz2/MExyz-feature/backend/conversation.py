"""ConversationState extraction, phase orchestration, and gate rules."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import prompt
from llm_service import LLMError, chat_json

_DEFAULT_COVERAGE = {
    "decision": False,
    "options": False,
    "fear_or_care": False,
    "constraint": False,
    "relationship_or_scene": False,
}

_GAP_ORDER = [
    ("decision", "当前具体决策（在选什么）"),
    ("options", "至少两条真实选项/方向"),
    ("fear_or_care", "核心恐惧或真正在乎之物"),
    ("constraint", "至少一个现实约束（钱/时间/家庭/期限等）"),
    ("relationship_or_scene", "关系影响或生活画面（二选一即可）"),
]

# Soft pacing: target ~8–10 user turns (see prompt.py + Skill §2)
PHASE_CONTAIN_MAX = 1
PHASE_CLARIFY_MAX = 3
PHASE_EXPLORE_MAX = 7

GATE_EMOTION_MIN_TURN = 5
GATE_WILLING_OFFER_TURN = 7
GATE_WILLING_AUTO_TURN = 8


def empty_state() -> dict[str, Any]:
    return {
        "phase": "contain",
        "decision": "",
        "options": [],
        "core_fear": "",
        "constraints": [],
        "relationship_hint": "",
        "scene_fragment": "",
        "summary_offered": False,
        "summary_confirmed": False,
        "future_explore_offered": False,
        "future_explore_accepted": False,
        "coverage": dict(_DEFAULT_COVERAGE),
    }


def _normalize_coverage(raw: dict | None) -> dict[str, bool]:
    cov = dict(_DEFAULT_COVERAGE)
    if isinstance(raw, dict):
        for k in cov:
            cov[k] = bool(raw.get(k))
    return cov


def merge_state(prev: dict | None, extracted: dict) -> dict[str, Any]:
    """Merge extracted state into previous; never delete non-empty fields."""
    base = empty_state()
    if prev:
        base.update({k: deepcopy(v) for k, v in prev.items() if k in base or k == "coverage"})
    if not base.get("coverage"):
        base["coverage"] = dict(_DEFAULT_COVERAGE)

    for key in (
        "phase",
        "decision",
        "core_fear",
        "relationship_hint",
        "scene_fragment",
    ):
        val = extracted.get(key)
        if isinstance(val, str) and val.strip():
            base[key] = val.strip()

    new_opts = extracted.get("options")
    if isinstance(new_opts, list):
        merged_opts = list(base.get("options") or [])
        for o in new_opts:
            if isinstance(o, str) and o.strip() and o.strip() not in merged_opts:
                merged_opts.append(o.strip())
        base["options"] = merged_opts[:4]

    new_constraints = extracted.get("constraints")
    if isinstance(new_constraints, list):
        merged_c = list(base.get("constraints") or [])
        for c in new_constraints:
            if isinstance(c, str) and c.strip() and c.strip() not in merged_c:
                merged_c.append(c.strip())
        base["constraints"] = merged_c[:4]

    for flag in (
        "summary_offered",
        "summary_confirmed",
        "future_explore_offered",
        "future_explore_accepted",
    ):
        if extracted.get(flag) is True:
            base[flag] = True

    ext_cov = _normalize_coverage(extracted.get("coverage"))
    prev_cov = _normalize_coverage(base.get("coverage"))
    base["coverage"] = {k: prev_cov[k] or ext_cov[k] for k in _DEFAULT_COVERAGE}

    # Reconcile coverage from field presence
    if base.get("decision"):
        base["coverage"]["decision"] = True
    if len(base.get("options") or []) >= 2:
        base["coverage"]["options"] = True
    if base.get("core_fear"):
        base["coverage"]["fear_or_care"] = True
    if base.get("constraints"):
        base["coverage"]["constraint"] = True
    if base.get("relationship_hint") or base.get("scene_fragment"):
        base["coverage"]["relationship_or_scene"] = True

    phase = extracted.get("phase")
    if phase in ("contain", "clarify", "explore", "summarize"):
        base["phase"] = phase

    return base


def extract_conversation_state(messages: list[dict], prev_state: dict | None) -> dict[str, Any]:
    """LLM extract + merge; on failure return prev or empty."""
    window = messages[-8:]
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in window)
    prev_json = json.dumps(prev_state or empty_state(), ensure_ascii=False)
    try:
        result = chat_json(
            [
                {
                    "role": "user",
                    "content": prompt.STATE_EXTRACT_PROMPT
                    + "\n\n上一轮档案 JSON：\n"
                    + prev_json
                    + "\n\n最近对话：\n"
                    + transcript,
                }
            ],
            temperature=0.2,
        )
        return merge_state(prev_state, result)
    except LLMError:
        return merge_state(prev_state, {}) if prev_state else empty_state()


def derive_phase(turn: int, coverage: dict[str, bool]) -> tuple[str, list[str]]:
    """Return (phase_label, missing_field_keys)."""
    cov = _normalize_coverage(coverage)
    missing = [k for k, _ in _GAP_ORDER if not cov.get(k)]

    if turn <= PHASE_CONTAIN_MAX:
        return "contain", missing
    if turn <= PHASE_CLARIFY_MAX:
        return "clarify", missing
    if turn <= PHASE_EXPLORE_MAX:
        return "explore", missing
    return "summarize", missing


def gate_from_state(state: dict, turn: int) -> dict[str, bool]:
    cov = _normalize_coverage(state.get("coverage"))

    info_complete = bool(
        cov.get("decision")
        and cov.get("options")
        and cov.get("fear_or_care")
        and cov.get("constraint")
    )

    emotion_stable = bool(state.get("summary_confirmed")) or (
        turn >= GATE_EMOTION_MIN_TURN
        and bool(state.get("summary_offered"))
        and state.get("phase") in ("explore", "summarize", "clarify")
    )

    user_willing = bool(state.get("future_explore_accepted"))
    if not user_willing and turn >= GATE_WILLING_OFFER_TURN and info_complete:
        if state.get("future_explore_offered") and turn >= GATE_WILLING_AUTO_TURN:
            user_willing = True
        elif state.get("future_explore_offered") and emotion_stable:
            user_willing = True

    return {
        "emotion_stable": emotion_stable,
        "info_complete": info_complete,
        "user_willing": user_willing,
    }


def monotonic_merge(old_gate: dict | None, new_gate: dict) -> dict[str, bool]:
    old = old_gate or {}
    return {
        "emotion_stable": bool(old.get("emotion_stable")) or bool(new_gate.get("emotion_stable")),
        "info_complete": bool(old.get("info_complete")) or bool(new_gate.get("info_complete")),
        "user_willing": bool(old.get("user_willing")) or bool(new_gate.get("user_willing")),
    }


def missing_labels(missing_keys: list[str]) -> list[str]:
    label_map = dict(_GAP_ORDER)
    return [label_map[k] for k in missing_keys if k in label_map]
