"""Seed a deterministic three-persona demo graph for syzhao42@163.com."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from braingraph.exporter import export_memory_events
from braingraph.graph_service import GraphBuilder
from braingraph.repository import CsvMemoryRepository
from braingraph.config import settings
from db import get_connection, init_db
from llm_service import chat
import store


TARGET_EMAIL = "syzhao42@163.com"

PERSONAS = [
    {
        "id": "demo_entrepreneur",
        "title": "创业者的我",
        "mood": "兴奋、务实、在不确定中快速验证",
        "accent": "ochre",
        "path": "从校园小项目走向真实创业",
        "day": "白天访谈用户，晚上和伙伴迭代产品",
        "cost": "时间压力、现金流焦虑与持续取舍",
        "system_prompt": "你是选择创业道路的未来自我，基于真实行动与复盘和现在的我对话。",
    },
    {
        "id": "demo_phd",
        "title": "读phd的我",
        "mood": "好奇、专注、偶尔焦虑",
        "accent": "plum",
        "path": "进入研究组，形成研究方向并持续发表",
        "day": "读论文、做实验、参加组会、写作和交流",
        "cost": "长反馈周期、研究不确定性与选校压力",
        "system_prompt": "你是正在攻读 PhD 的未来自我，围绕科研成长、选择与生活体验和现在的我对话。",
    },
    {
        "id": "demo_bigtech",
        "title": "进大厂的我",
        "mood": "稳定、进取、重视协作和影响力",
        "accent": "slate",
        "path": "通过实习与校招进入大型科技公司",
        "day": "参加评审、写代码、看指标、跨团队协作",
        "cost": "绩效压力、组织沟通与个人方向取舍",
        "system_prompt": "你是进入大型科技公司的未来自我，围绕工程成长、组织协作与职业选择和现在的我对话。",
    },
]

EVENTS = {
    "demo_entrepreneur": [
        ("2022-10-16T14:00:00+08:00", "大一时我自学前端，搭了一个帮助同学整理课程资料的小网站", "第一次独立把需求做成可使用的页面，让我发现自己喜欢创造能解决身边问题的东西。", [("joy", "喜悦", 0.78), ("optimism", "乐观", 0.7)]),
        ("2023-03-25T16:00:00+08:00", "我主动找二十位同学访谈，了解他们使用课程网站时真正遇到的困难", "具体反馈让我意识到，先理解别人为什么需要，比急着增加功能更重要。", [("surprise", "惊讶", 0.62), ("satisfaction", "满足", 0.58)]),
        ("2023-11-12T19:00:00+08:00", "大二时我在创新社团认识了两位伙伴，一起做校园二手交换工具", "第一次持续和伙伴协作，让我开始学习分工、承诺与及时沟通。", [("optimism", "乐观", 0.75), ("anxiety", "焦虑", 0.43)]),
        ("2024-07-20T09:00:00+08:00", "我和队友参加 AdventureX 黑客松，在两天内完成并展示了产品原型", "有限时间里的取舍让我体会到，完成核心闭环比堆叠功能更有价值。", [("joy", "喜悦", 0.84), ("anxiety", "焦虑", 0.55)]),
        ("2024-09-18T15:30:00+08:00", "我把黑客松原型带回校园测试，并根据反馈连续迭代了三个版本", "持续观察真实使用情况，让我开始用验证结果而不是个人偏好做决定。", [("satisfaction", "满足", 0.76), ("confusion", "迷茫", 0.36)]),
        ("2024-12-08T18:30:00+08:00", "我邀请一位创业学长喝咖啡，认真询问早期团队、现金流和失败经历", "这次交流让我看到创业的现实成本，也让我愿意更审慎地准备而不是浪漫化选择。", [("calm", "平静", 0.63), ("anxiety", "焦虑", 0.42)]),
        ("2025-03-15T11:00:00+08:00", "大三产品实习中，我跟着导师完成了用户调研、需求取舍和上线复盘", "完整参与产品流程，让我补上了从想法到交付之间的系统方法。", [("satisfaction", "满足", 0.81), ("optimism", "乐观", 0.67)]),
        ("2025-06-28T14:30:00+08:00", "我用课余项目争取到一个校园组织的小额付费试点", "第一次有人愿意为解决方案付费，让我更具体地理解价值验证，也更想探索创业道路。", [("joy", "喜悦", 0.86), ("calm", "平静", 0.61)]),
    ],
    "demo_phd": [
        ("2022-11-05T10:00:00+08:00", "大一参加实验室开放日时，我第一次近距离看到学长展示研究项目", "研究把好奇心变成可检验的问题，这种工作方式让我产生了持续了解的兴趣。", [("surprise", "惊讶", 0.72), ("optimism", "乐观", 0.65)]),
        ("2023-05-14T20:00:00+08:00", "我认真完成统计与编程课程，并用课程项目复现了一篇论文里的简单实验", "复现过程让我体会到证据、方法和细节的重要，也发现自己能享受长时间钻研。", [("satisfaction", "满足", 0.73), ("anxiety", "焦虑", 0.38)]),
        ("2023-10-21T14:00:00+08:00", "大二我主动给老师写邮件，申请成为实验室本科研究助理", "主动争取机会需要承认自己的不足，也让我开始学习如何清楚表达兴趣和准备。", [("anxiety", "焦虑", 0.61), ("optimism", "乐观", 0.66)]),
        ("2024-01-13T16:30:00+08:00", "我加入每周文献阅读小组，第一次完整讲解并讨论一篇论文", "公开表达暴露了理解中的空白，也让我逐渐学会提出更具体的问题。", [("anxiety", "焦虑", 0.58), ("satisfaction", "满足", 0.55)]),
        ("2024-06-22T11:00:00+08:00", "我协助整理实验数据，并在老师指导下排查了一次复现失败", "失败并非没有价值，规范记录和耐心验证能把困惑转化为下一步线索。", [("confusion", "迷茫", 0.57), ("calm", "平静", 0.5)]),
        ("2024-08-30T15:00:00+08:00", "暑研期间我负责一个小问题，并在结项展示中汇报初步结果", "独立推进小问题让我更清楚研究节奏，也确认自己愿意面对较长的反馈周期。", [("joy", "喜悦", 0.75), ("anxiety", "焦虑", 0.45)]),
        ("2025-02-16T19:30:00+08:00", "大三我完成本科研究计划书，反复修改研究问题和实验设计", "把模糊兴趣压缩成可研究的问题，让我看见自己在论证和方法上的成长空间。", [("satisfaction", "满足", 0.71), ("confusion", "迷茫", 0.4)]),
        ("2025-06-09T17:00:00+08:00", "我和不同学校的在读博士交流，开始整理适合自己的研究方向与申请准备", "真实交流让我不再只看排名，而是关注研究匹配、指导方式和自己是否愿意长期投入。", [("optimism", "乐观", 0.7), ("calm", "平静", 0.58)]),
    ],
    "demo_bigtech": [
        ("2022-09-24T15:00:00+08:00", "大一编程课上，我第一次独立完成一个能稳定运行的小程序", "从报错到跑通的过程让我获得成就感，也愿意继续打牢工程基础。", [("joy", "喜悦", 0.73), ("optimism", "乐观", 0.62)]),
        ("2023-04-09T13:30:00+08:00", "我加入校园开源项目，第一次按照规范提交代码并接受代码审查", "别人对代码的反馈让我理解，可读性、测试和协作习惯与功能正确同样重要。", [("anxiety", "焦虑", 0.48), ("satisfaction", "满足", 0.57)]),
        ("2023-12-02T20:00:00+08:00", "大二我系统学习数据结构与计算机网络，并为薄弱知识建立复习计划", "持续补基础让我从追求快速答案，转向理解系统为什么这样工作。", [("calm", "平静", 0.58), ("satisfaction", "满足", 0.65)]),
        ("2024-05-18T10:00:00+08:00", "我在校内技术比赛中负责后端，与三位同学协作完成服务部署", "接口约定、进度同步和故障排查让我第一次感受到团队工程的节奏。", [("joy", "喜悦", 0.68), ("anxiety", "焦虑", 0.54)]),
        ("2024-09-07T19:00:00+08:00", "我开始准备技术实习，把零散项目整理成可以说明设计取舍的作品集", "准备过程让我意识到，真正重要的不只是做过什么，还包括为什么这样设计。", [("confusion", "迷茫", 0.44), ("optimism", "乐观", 0.63)]),
        ("2025-01-20T10:30:00+08:00", "大三寒假我进入科技公司实习，完成了第一个进入测试环境的需求", "真实代码库让我看到可靠交付所需的细节，也让我愿意适应更严格的工程标准。", [("joy", "喜悦", 0.77), ("anxiety", "焦虑", 0.56)]),
        ("2025-03-12T17:30:00+08:00", "实习中我根据代码审查意见补充测试，并参与了一次问题复盘", "面对反馈时从防御转向理解系统风险，让我开始形成更成熟的工程责任感。", [("satisfaction", "满足", 0.69), ("calm", "平静", 0.52)]),
        ("2025-06-21T16:00:00+08:00", "我结合实习体验比较不同技术方向，开始准备秋招并主动联系学长了解团队", "我不再只追求公司名气，而是更关注成长环境、问题价值与适合自己的工作方式。", [("optimism", "乐观", 0.72), ("confusion", "迷茫", 0.39)]),
    ],
}


def iso_label(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y年%m月%d日")


def generate_growth_summaries(user_id: str) -> dict[str, str]:
    persona_titles = {item["id"]: item["title"] for item in PERSONAS}
    summaries: dict[str, str] = {}
    system_prompt = """
你是一位克制、温和、尊重事实的成长叙事分析师。请根据同一身份分支从起点到当前节点的完整记录，
写一段连续的中文成长与心路历程总结。

要求：
1. 必须综合输入中的当前节点及此前所有节点，包括每个节点的事件、情绪及强度、观点，以及前序节点已经生成的成长总结。
2. 按时间呈现用户的行动、感受、理解和选择如何逐步变化，并指出不同阶段之间的联系。
3. 只能依据材料，不能虚构经历、动机、人格判断或确定性的因果关系；推断要使用审慎措辞。
4. 语言平和、具体、有同理心，不煽情、不评判、不写鸡汤，不使用标题、项目符号、Markdown 或星号。
5. 正文长度必须不少于200个且不超过300个中文字符，包含标点；目标长度为230至270字。
6. 只输出总结正文，不要解释规则，不要附加字数。
""".strip()
    for persona_id, events in EVENTS.items():
        history = []
        for index, (event_time, content, viewpoint, emotions) in enumerate(events, 1):
            event_id = f"{persona_id}_event_{index:02d}"
            history.append(
                {
                    "date": event_time,
                    "event": content,
                    "emotions": [
                        {"label": label, "intensity": intensity}
                        for _, label, intensity in emotions
                    ],
                    "viewpoint": viewpoint,
                    "growth_summary": "",
                }
            )
            prompt = (
                f"身份分支：{persona_titles[persona_id]}\n"
                f"当前节点：{event_id}\n"
                "以下是从分支起点到当前节点的全部材料。请严格根据材料总结：\n"
                + json.dumps(history, ensure_ascii=False, indent=2)
            )
            summary = ""
            for attempt in range(3):
                request = prompt
                if attempt:
                    request += (
                        f"\n\n上一版长度为{len(summary)}字，不符合200至300字要求。"
                        "请保留事实并重写为230至270字。"
                    )
                summary = chat(
                    [{"role": "user", "content": request}],
                    system=system_prompt,
                    temperature=0.4,
                ).replace("*", "").strip()
                if 200 <= len(summary) <= 300:
                    break
            if len(summary) > 300:
                sentence_ends = [
                    position + 1
                    for position, character in enumerate(summary[:300])
                    if character in "。！？" and position + 1 >= 200
                ]
                summary = summary[: sentence_ends[-1] if sentence_ends else 300].strip()
            if not 200 <= len(summary) <= 300:
                raise RuntimeError(
                    f"{event_id} growth summary length {len(summary)} is outside 200-300"
                )
            summaries[event_id] = summary
            history[-1]["growth_summary"] = summary
    return summaries


def seed_role_chat(user_id: str, persona: dict, session_id: str) -> None:
    events = EVENTS[persona["id"]]
    event = lambda index: events[index][1]
    viewpoint = lambda index: events[index][2]
    dialogue = [
        ("我们先从最早的起点聊起。你第一次对这条未来路径产生兴趣，是什么经历？",
         f"应该是{event(0)}。{viewpoint(0)}"),
        ("当时你没有只停留在兴趣上，接下来主动做了什么？",
         f"后来{event(1)}。我想确认自己的兴趣能不能落到真实行动里。"),
        ("这个过程中，最先让你感到不确定的地方是什么？",
         f"{event(2)}的时候我有些焦虑，因为很多事情需要和别人配合，也不能只按自己的节奏来。"),
        ("你是怎么回应这种不确定，而不是直接放弃的？",
         f"我选择继续参与，并把任务拆小、及时沟通。{viewpoint(2)}"),
        ("有没有一次经历，让你明显感觉到团队协作的重要？",
         f"有，{event(3)}。那次让我看到，清楚分工和共同完成闭环比个人表现更重要。"),
        ("那次经历具体改变了你做事的哪种习惯？",
         f"我开始先确认目标和限制，再决定投入什么。{viewpoint(3)}"),
        ("之后你如何验证，这条路不是一时兴起？",
         f"我继续做了下一步：{event(4)}。持续投入后，我发现自己仍愿意处理细节和反馈。"),
        ("收到外部反馈时，你的情绪和想法有什么变化？",
         f"一开始会迷茫，担心之前的判断不够好；但{viewpoint(4)}"),
        ("你有没有主动向更有经验的人求证自己的理解？",
         f"有，{event(5)}。我想听到真实成本，而不只是成功故事。"),
        ("那次交流后，你对这条未来路径少了什么幻想，又多了什么认识？",
         f"我少了一些理想化想象，也更重视长期准备。{viewpoint(5)}"),
        ("在本科阶段，你补上的最关键能力是什么？",
         f"{event(6)}让我补上了系统方法，也让我知道课堂知识怎样进入真实场景。"),
        ("有没有一个结果，让你觉得自己的准备开始形成证据？",
         f"有，{event(7)}。它不是最终答案，但说明之前积累的能力开始能解决真实问题。"),
        ("回看这些经历，你觉得自己最大的变化是什么？",
         f"我从等待确定答案，变成愿意先做小规模尝试、听反馈再调整。{viewpoint(7)}"),
        ("目前你仍然欠缺什么？如果继续准备，你最想补哪一块？",
         f"我还缺少更长期、更复杂场景下的经验。下一步想继续补基础，也观察自己能否稳定投入。"),
        ("最后，如果把这些经历放在一起，它们为什么会让你认真考虑成为“未来的{title}”？",
         f"因为这些事件不是一次冲动：从{event(0)}到{event(7)}，我反复体验了这条路的行动方式、压力和成就感，仍然愿意继续靠近它。"),
    ]
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM messages WHERE user_id = ? AND session_id = ? "
            "AND id LIKE 'demo_msg_%'",
            (user_id, session_id),
        )
        base_time = datetime(2025, 7, 1, 19, 0, tzinfo=timezone(timedelta(hours=8)))
        for index, (assistant_text, user_text) in enumerate(dialogue, 1):
            assistant_text = assistant_text.format(title=persona["title"])
            question_time = base_time + timedelta(minutes=(index - 1) * 4)
            rows = [
                (
                    f"demo_msg_{persona['id']}_{index:02d}_a",
                    "assistant",
                    assistant_text,
                    question_time.isoformat(),
                ),
                (
                    f"demo_msg_{persona['id']}_{index:02d}_u",
                    "user",
                    user_text,
                    (question_time + timedelta(minutes=1)).isoformat(),
                ),
            ]
            for message_id, role, content_text, ts in rows:
                conn.execute(
                    """INSERT INTO messages
                       (id, session_id, user_id, role, content, ts)
                       VALUES (?,?,?,?,?,?)""",
                    (message_id, session_id, user_id, role, content_text, ts),
                )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    init_db()
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (TARGET_EMAIL,)
        ).fetchone()
    finally:
        conn.close()
    if not user:
        raise SystemExit(f"Target account does not exist: {TARGET_EMAIL}")
    user_id = user["id"]
    growth_summaries = generate_growth_summaries(user_id)

    persona_rows = []
    for persona in PERSONAS:
        row = dict(persona)
        row["source_session_id"] = "main_1"
        row["created_at"] = "2025-01-01T00:00:00+08:00"
        persona_rows.append(row)
    store.upsert_personas(user_id, persona_rows)

    seeded_ids = []
    for persona in PERSONAS:
        persona_id = persona["id"]
        role = store.ensure_role_session(user_id, persona_id)
        session_id = role["session_id"]
        previous_id = None
        for index, (event_time, content, viewpoint, emotions) in enumerate(
            EVENTS[persona_id], 1
        ):
            event_id = f"{persona_id}_event_{index:02d}"
            seeded_ids.append(event_id)
            event = {
                "event_id": event_id,
                "event_time": iso_label(event_time),
                "event_time_iso": event_time,
                "event": content,
                "emotions": [label for _, label, _ in emotions],
                "emotion_details": [
                    {
                        "code": code,
                        "label": label,
                        "intensity": intensity,
                        "score": intensity,
                    }
                    for code, label, intensity in emotions
                ],
                "viewpoint": viewpoint,
                "world": "future",
                "branch_id": persona_id,
                "source_session_id": session_id,
                "source_turn_id": f"{session_id}-simulated-turn-{index:02d}",
                "parent_event_id": previous_id,
                "branch_origin_event_id": None,
                "growth_summary": growth_summaries[event_id],
                "evidence": [
                    f"模拟对话：现在的我与{persona['title']}的第 {index} 轮交流",
                    f"结构化事件：{content}",
                ],
                "created_at": event_time,
            }
            store.upsert_event(user_id, event)
            store.project_event_to_mindmap(user_id, event)
            previous_id = event_id
        seed_role_chat(user_id, persona, session_id)

    csv_path = export_memory_events()
    records = CsvMemoryRepository(csv_path).list_events(user_id)
    graph = GraphBuilder().build(records)
    branch_labels = [
        node.label for node in graph.nodes if node.type == "branch_anchor"
    ]
    result = {
        "email": TARGET_EMAIL,
        "user_id": user_id,
        "personas": [persona["title"] for persona in PERSONAS],
        "events_written": len(seeded_ids),
        "chat_messages_written": len(PERSONAS) * 15 * 2,
        "csv_path": str(csv_path),
        "csv_events_for_user": len(records),
        "graph_stats": graph.stats.model_dump(),
        "branch_labels": branch_labels,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
