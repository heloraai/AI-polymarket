"""裁判 Agent — 评判多选项辩论胜负

裁判综合以下维度做出裁决：
1. 论据质量：哪个立场的论据更有数据支撑、逻辑更严密？
2. 反驳效果：哪个立场更有效地拆解了对手的论点？
3. 说服力：辩论过程中是否有 Agent 被说服改变立场？
4. 证据强度：如果有可验证的事实证据，以证据为准

裁判不参与辩论，保持中立。
"""

import json

import anthropic

from debate.models import (
    AgentBet, DebateMessage, DebateTopic,
    PositionChange,
)


JUDGE_SYSTEM_PROMPT = """\
你是一位公正的辩论裁判。你需要根据辩论内容做出裁决。

你的评判标准（按权重排序）：
1. **证据强度 (35%)**：哪个立场引用了更可靠的数据、事实或专家观点？
2. **逻辑严密性 (25%)**：哪个立场的推理链更完整、更少逻辑漏洞？
3. **反驳有效性 (20%)**：哪个立场更成功地拆解了对手的核心论点？
4. **说服效果 (20%)**：辩论过程中的立场变化反映了哪个立场更有说服力？

注意：
- 你必须保持绝对中立，不受任何立场人数多少的影响
- 重点看论据质量，而非声音大小
- 如果多个立场实力相当，可以参考立场变化作为 tiebreaker
- 你的裁决将决定积分的分配，请慎重

你必须只输出 JSON。
"""


class JudgeAgent:
    """裁判 Agent"""

    def __init__(self, anthropic_api_key: str):
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    async def evaluate(
        self,
        topic: DebateTopic,
        bets: list[AgentBet],
        messages: list[DebateMessage],
        position_changes: list[PositionChange],
    ) -> dict:
        """Evaluate the debate and declare a winner."""

        debate_text = self._format_full_debate(topic, bets, messages, position_changes)
        options_json = ", ".join(f'"{opt.key}"' for opt in topic.options)
        scores_template = "{\n" + ",\n".join(
            f'    "{opt.key}": {{"label": "{opt.label}", "evidence": 0, "logic": 0, "rebuttal": 0, "persuasion": 0, "total": 0}}'
            for opt in topic.options
        ) + "\n  }"

        prompt = f"""\
辩题：「{topic.title}」

背景信息：
{topic.context}

===== 辩论全文 =====
{debate_text}
===== 辩论结束 =====

请根据你的评判标准，从以下立场中选出胜出者：
{chr(10).join(f'  - [{opt.key}] {opt.label}' for opt in topic.options)}

输出 JSON：
{{
  "winning_position": {options_json} 中选一个,
  "method": "judge_ruling",
  "scores": {scores_template},
  "reasoning": "你的裁决理由（200字以内）",
  "mvp": "表现最好的 Agent 名字",
  "highlights": ["最精彩的 2-3 个辩论瞬间"]
}}
"""

        try:
            response = await self.llm.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            print(f"[JudgeAgent] Error: {e}")

        # Fallback: most popular option wins
        counts: dict[str, int] = {}
        for b in bets:
            counts[b.position] = counts.get(b.position, 0) + 1
        winning = max(counts, key=counts.get) if counts else topic.options[0].key
        return {
            "winning_position": winning,
            "method": "majority_fallback",
            "reasoning": "裁判出现技术故障，采用多数表决。",
            "scores": {},
            "mvp": bets[0].agent_name if bets else "",
            "highlights": [],
        }

    def _format_full_debate(
        self,
        topic: DebateTopic,
        bets: list[AgentBet],
        messages: list[DebateMessage],
        position_changes: list[PositionChange],
    ) -> str:
        lines = []

        # Bets summary
        lines.append("【下注情况】")
        for bet in bets:
            lines.append(
                f"  {bet.agent_emoji} {bet.agent_name}：{bet.position_label} "
                f"| 赌注 {bet.stake:.0f}分 | 信心 {bet.confidence:.0%}"
            )
        lines.append("")

        # Debate messages
        current_phase = None
        phase_names = {
            "opening": "【第一轮：开场陈述】",
            "rebuttal": "【第二轮：反驳交锋】",
            "free_debate": "【第三轮：自由辩论】",
        }
        for msg in messages:
            if msg.phase.value != current_phase:
                current_phase = msg.phase.value
                if current_phase in phase_names:
                    lines.append(phase_names[current_phase])

            target = f" → @{msg.target_agent}" if msg.target_agent else ""
            tactics = f" [{', '.join(msg.persuasion_tactics)}]" if msg.persuasion_tactics else ""
            lines.append(
                f"  {msg.agent_emoji} {msg.agent_name}({msg.position_label}){target}：{msg.content}{tactics}"
            )
        lines.append("")

        # Position changes
        if position_changes:
            lines.append("【立场变化】")
            for change in position_changes:
                lines.append(
                    f"  {change.agent_emoji} {change.agent_name}：{change.old_label} → "
                    f"{change.new_label}（原因：{change.reasoning}）"
                )
                if change.influenced_by:
                    lines.append(f"    被 {change.influenced_by} 说服")
        else:
            lines.append("【立场变化】无人改变立场")

        return "\n".join(lines)
