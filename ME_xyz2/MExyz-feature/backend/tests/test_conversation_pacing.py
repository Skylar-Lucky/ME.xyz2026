"""Unit tests for fixed 10-turn pacing and gate rules."""

import conversation


def _cov(**flags):
    base = {
        "decision": False,
        "options": False,
        "fear_or_care": False,
        "constraint": False,
        "relationship_or_scene": False,
    }
    base.update(flags)
    return base


def test_derive_phase_bounds():
    empty = _cov()
    assert conversation.derive_phase(1, empty)[0] == "contain"
    assert conversation.derive_phase(2, empty)[0] == "clarify"
    assert conversation.derive_phase(3, empty)[0] == "clarify"
    assert conversation.derive_phase(4, empty)[0] == "explore"
    assert conversation.derive_phase(8, empty)[0] == "explore"
    assert conversation.derive_phase(9, empty)[0] == "summarize"
    assert conversation.derive_phase(10, empty)[0] == "summarize"


def test_missing_follows_gap_order():
    cov = _cov(decision=True, options=True)
    phase, missing = conversation.derive_phase(5, cov)
    assert phase == "explore"
    assert missing[0] == "fear_or_care"
    assert missing == [
        "fear_or_care",
        "constraint",
        "relationship_or_scene",
    ]


def test_gate_not_ready_before_turn_10_even_if_flags_set():
    state = conversation.empty_state()
    state["coverage"] = _cov(
        decision=True,
        options=True,
        fear_or_care=True,
        constraint=True,
        relationship_or_scene=True,
    )
    state["summary_offered"] = True
    state["summary_confirmed"] = True
    state["future_explore_offered"] = True
    state["future_explore_accepted"] = True
    state["phase"] = "summarize"

    gate = conversation.gate_from_state(state, turn=9)
    assert gate["user_willing"] is False
    assert not (gate["emotion_stable"] and gate["info_complete"] and gate["user_willing"])


def test_gate_forced_ready_at_turn_10():
    state = conversation.empty_state()
    gate = conversation.gate_from_state(state, turn=10)
    assert gate == {
        "emotion_stable": True,
        "info_complete": True,
        "user_willing": True,
    }


def test_gate_forced_ready_after_turn_10():
    state = conversation.empty_state()
    gate = conversation.gate_from_state(state, turn=11)
    assert gate["user_willing"] is True
    assert conversation.is_chat_closed(11) is True
    assert conversation.is_chat_closed(10) is False


def test_info_complete_still_tracks_coverage_before_turn_10():
    state = conversation.empty_state()
    state["coverage"] = _cov(
        decision=True,
        options=True,
        fear_or_care=True,
        constraint=True,
    )
    gate = conversation.gate_from_state(state, turn=6)
    assert gate["info_complete"] is True
    assert gate["user_willing"] is False
