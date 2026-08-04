"""Prompt-level guardrails for natural main-chat dialogue."""

import prompt


def _system(turn: int, phase: str, missing: list[str]) -> str:
    state = {
        "coverage": {},
        "options": [],
    }
    return prompt.build_main_chat_system(turn, phase, state, missing)


def test_main_system_forbids_repetitive_openings_and_consecutive_binary_questions():
    assert "禁止机械复读" in prompt.MAIN_CHAT_SYSTEM
    assert "严禁连续两轮使用二选一句式" in prompt.MAIN_CHAT_SYSTEM
    assert "用户表达清楚时直接沿着他的逻辑推进" in prompt.MAIN_CHAT_SYSTEM


def test_priority_hints_use_open_questions_instead_of_binary_templates():
    hints = "\n".join(
        line
        for priority in (
            "decision",
            "options",
            "fear_or_care",
            "constraint",
            "relationship_or_scene",
        )
        for line in prompt._priority_hint(priority, has_options_anchor=False)
    )

    assert "开放式" in hints
    assert "是卡在一个具体选择上，还是" not in hints
    assert "更怕失去的是稳定，还是" not in hints
    assert "不得照抄或固定轮换" in hints


def test_turn_nine_uses_natural_summary_not_fixed_fill_in_template():
    system = _system(9, "summarize", [])

    assert "本轮必须执行【总结镜像】" in system
    assert "严禁探索新技术、新方向或任何新维度" in system
    assert "只允许结尾一个低压力校准问句" in system
    assert "自然梳理" in system
    assert "低压力" in system
    assert "你想要 __，但不想以 __ 为代价" not in system
    assert "上述总结句式" not in system
    assert "本轮内部目标" not in system


def test_prompt_forbids_unconfirmed_inference_as_fact():
    system = _system(9, "summarize", [])

    assert "未确认的理解" in system
    assert "不得写成事实" in system
    assert "用户没有明确表达的代价、偏好、动机或情绪" in system
    assert "大模型可能加班但赚钱" not in system
    assert "不想以加班为代价" not in system


def test_turn_nine_does_not_weave_missing_fields_into_summary():
    system = _system(9, "summarize", ["constraint"])

    assert "缺失维度保持未知" in system
    assert "只总结已有明确依据的内容" in system
    assert "织进总结" not in system


def test_turn_ten_keeps_denial_tolerance_and_button_handoff():
    system = _system(10, "summarize", [])

    assert "否定总结" in system
    assert "不得开启任何新的探索问题" in system
    assert "严禁提出任何问句" in system
    assert "不允许出现问号" in system
    assert "对吗" not in system
    assert (
        "请点击下方按钮，生成「未来的自己」，看看三年后平行时空里的不同可能。"
        in system
    )


def test_persona_generator_prioritizes_transcript_and_requires_concrete_anchors():
    skill = prompt.PERSONA_GEN_SKILL

    assert "完整对话记录优先" in skill
    assert "ConversationState 辅助" in skill
    assert "内部静默提取" in skill
    assert "每张 persona 至少自然使用 2 个" in skill
    assert "三张卡合计覆盖" in skill
    assert "最新用户纠正" in skill
    assert "若遮掉职业名后仍可套给任意用户" in skill
    assert "重写该卡" in skill
    assert "不能降低每张卡至少两个真实锚点的要求" in skill
    assert "优先从档案中的 options" not in skill
    assert "优先从完整对话锚点" in skill


def test_persona_generator_binds_path_day_and_cost_without_case_contamination():
    skill = prompt.PERSONA_GEN_SKILL
    all_prompts = prompt.MAIN_CHAT_SYSTEM + skill

    assert "`path`" in skill
    assert "`day`" in skill
    assert "`cost`" in skill
    assert "AI PM" not in all_prompts
    assert "RAG" not in all_prompts
    assert "模型微调" not in all_prompts
    assert "大模型可能加班但赚钱" not in all_prompts
