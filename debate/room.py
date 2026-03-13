"""辩论室 — Agent 观点擂台的核心引擎

流程：
1. 选题：从知乎热榜选取话题，转化为 YES/NO 辩题
2. 下注：每个 Agent 根据性格选择立场并下注积分
3. 辩论：3轮辩论（开场陈述 → 反驳 → 自由辩论）
4. 立场更新：辩论后 Agent 可以被说服改变立场
5. 裁决：裁判综合证据质量 + 立场变化判定胜负
6. 结算：赢家瓜分输家的积分池
"""

import asyncio
import json
import random
import uuid
from datetime import datetime
from typing import Callable, Optional

import anthropic

from agents.personalities import AgentPersonality, ALL_PERSONALITIES
from debate.models import (
    AgentBet, DebateEvent, DebateMessage, DebatePhase,
    DebateResult, DebateTopic, Position, PositionChange,
)


class DebateRoom:
    """辩论室：管理一场完整的 Agent 辩论"""

    def __init__(
        self,
        topic: DebateTopic,
        personalities: list[AgentPersonality] | None = None,
        anthropic_api_key: str = "",
        initial_stake: float = 100.0,
    ):
        self.topic = topic
        self.personalities = personalities or ALL_PERSONALITIES
        self.api_key = anthropic_api_key
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.initial_stake = initial_stake

        # State
        self.phase = DebatePhase.WAITING
        self.bets: list[AgentBet] = []
        self.messages: list[DebateMessage] = []
        self.position_changes: list[PositionChange] = []
        self.events: list[DebateEvent] = []

        # Callbacks for real-time updates
        self._event_callback: Optional[Callable] = None

    def on_event(self, callback: Callable):
        """Register callback for real-time events (WebSocket push)."""
        self._event_callback = callback

    async def _emit(self, event_type: str, data: dict):
        """Emit an event to the frontend."""
        event = DebateEvent(
            type=event_type,
            phase=self.phase,
            data=data,
        )
        self.events.append(event)
        if self._event_callback:
            await self._event_callback(event)

    async def run(self) -> DebateResult:
        """Run the full debate flow."""
        # Phase 1: Betting
        await self._betting_phase()

        # Phase 2: Opening statements
        await self._debate_round(1, DebatePhase.OPENING)

        # Phase 3: Rebuttals
        await self._debate_round(2, DebatePhase.REBUTTAL)

        # Phase 4: Free debate
        await self._debate_round(3, DebatePhase.FREE_DEBATE)

        # Phase 5: Position updates (agents can change sides)
        await self._position_update_phase()

        # Phase 6: Resolution
        result = await self._resolution_phase()

        return result

    # ── Phase 1: Betting ─────────────────────────────────

    async def _betting_phase(self):
        """Each agent picks a side and places a bet."""
        self.phase = DebatePhase.BETTING
        await self._emit("phase_change", {"phase": "betting", "label": "下注阶段"})

        # Randomize order
        agents = list(self.personalities)
        random.shuffle(agents)

        for personality in agents:
            decision = await self._agent_bet(personality)
            bet = AgentBet(
                agent_name=personality.name,
                agent_emoji=personality.emoji,
                position=Position.YES if decision["position"] == "YES" else Position.NO,
                stake=self.initial_stake,
                confidence=decision.get("confidence", 0.5),
                reasoning=decision.get("reasoning", ""),
            )
            self.bets.append(bet)
            await self._emit("bet", {
                "agent_name": personality.name,
                "agent_emoji": personality.emoji,
                "position": bet.position.value,
                "stake": bet.stake,
                "confidence": bet.confidence,
                "reasoning": bet.reasoning,
            })

    async def _agent_bet(self, personality: AgentPersonality) -> dict:
        """Ask an agent to pick a side for the debate."""
        prompt = f"""\
你正在参加一场辩论赛。辩题是：

「{self.topic.title}」

背景信息：
{self.topic.context}

你需要选择一个立场（YES 或 NO），并准备为这个立场辩护。
你将投入 {self.initial_stake} 积分作为赌注。如果你的立场最终获胜，你将赢得对方的积分。

根据你的性格特点，选择你认为正确的立场。

输出 JSON：
{{
  "position": "YES" 或 "NO",
  "confidence": 0.0-1.0,
  "reasoning": "你选择这个立场的原因（一句话）"
}}
"""
        return await self._call_llm(personality, prompt)

    # ── Phase 2-4: Debate Rounds ─────────────────────────

    async def _debate_round(self, round_num: int, phase: DebatePhase):
        """Run a single debate round."""
        self.phase = phase
        phase_labels = {
            DebatePhase.OPENING: "开场陈述",
            DebatePhase.REBUTTAL: "反驳交锋",
            DebatePhase.FREE_DEBATE: "自由辩论",
        }
        await self._emit("phase_change", {
            "phase": phase.value,
            "label": phase_labels.get(phase, phase.value),
            "round": round_num,
        })

        # Determine speaking order: alternate YES/NO for drama
        yes_agents = [p for p in self.personalities if self._get_position(p.name) == Position.YES]
        no_agents = [p for p in self.personalities if self._get_position(p.name) == Position.NO]
        random.shuffle(yes_agents)
        random.shuffle(no_agents)

        # Interleave: YES, NO, YES, NO, ...
        speaking_order = []
        max_len = max(len(yes_agents), len(no_agents))
        for i in range(max_len):
            if i < len(yes_agents):
                speaking_order.append(yes_agents[i])
            if i < len(no_agents):
                speaking_order.append(no_agents[i])

        for personality in speaking_order:
            message = await self._agent_speak(personality, round_num, phase)
            if message:
                self.messages.append(message)
                await self._emit("message", {
                    "id": message.id,
                    "agent_name": message.agent_name,
                    "agent_emoji": message.agent_emoji,
                    "position": message.position.value,
                    "content": message.content,
                    "round_num": round_num,
                    "phase": phase.value,
                    "target_agent": message.target_agent,
                    "tactics": message.persuasion_tactics,
                })

    async def _agent_speak(
        self, personality: AgentPersonality, round_num: int, phase: DebatePhase
    ) -> DebateMessage | None:
        """Generate a debate message from an agent."""
        position = self._get_position(personality.name)
        if position is None:
            return None

        # Build debate context
        debate_history = self._format_debate_history()
        other_bets = self._format_bets(exclude=personality.name)

        phase_instructions = {
            DebatePhase.OPENING: (
                "这是开场陈述阶段。请清晰阐述你的立场和核心论据。"
                "要有气势，要让对手知道你不好惹。"
                "限制在 2-3 个核心论点内。"
            ),
            DebatePhase.REBUTTAL: (
                "这是反驳阶段。你需要：\n"
                "1. 针对对方阵营的核心论据进行反驳\n"
                "2. 指出对方逻辑中的漏洞\n"
                "3. 用数据或案例加强自己的论点\n"
                "你可以点名反驳某个特定的 Agent。要犀利但有理有据。"
            ),
            DebatePhase.FREE_DEBATE: (
                "这是自由辩论阶段，最后的交锋机会！你可以：\n"
                "1. 发起新的攻击角度\n"
                "2. 总结性地摧毁对方的论点\n"
                "3. 尝试说服对方阵营中立场不坚定的 Agent 转变立场\n"
                "4. 做出有力的总结陈词\n"
                "这是你最后的机会，要全力以赴！"
            ),
        }

        prompt = f"""\
辩题：「{self.topic.title}」

背景信息：
{self.topic.context}

你的立场：{position.value}（{'支持' if position == Position.YES else '反对'}）

其他 Agent 的下注情况：
{other_bets}

{'之前的辩论记录：' + chr(10) + debate_history if debate_history else '（这是第一轮发言）'}

{phase_instructions.get(phase, '')}

要求：
- 用你的性格特点来辩论（{personality.description}）
- 发言控制在 150 字以内，简短有力
- 可以用反问、类比、数据等修辞手法
- 如果要针对某个 Agent 反驳，请点名

输出 JSON：
{{
  "content": "你的辩论发言",
  "target_agent": "你要反驳的 Agent 名字，没有则为 null",
  "tactics": ["使用的辩论策略，如：类比论证、数据反驳、情感诉求、归谬法"]
}}
"""
        result = await self._call_llm(personality, prompt)

        return DebateMessage(
            agent_name=personality.name,
            agent_emoji=personality.emoji,
            position=position,
            content=result.get("content", "..."),
            round_num=round_num,
            phase=phase,
            target_agent=result.get("target_agent"),
            persuasion_tactics=result.get("tactics", []),
        )

    # ── Phase 5: Position Update ────────────────────────

    async def _position_update_phase(self):
        """After debate, agents can change their position if persuaded."""
        self.phase = DebatePhase.POSITION_UPDATE
        await self._emit("phase_change", {
            "phase": "position_update",
            "label": "立场更新",
        })

        debate_history = self._format_debate_history()

        for personality in self.personalities:
            current_position = self._get_position(personality.name)
            if current_position is None:
                continue

            prompt = f"""\
辩题：「{self.topic.title}」

你的当前立场：{current_position.value}

完整辩论记录：
{debate_history}

辩论已经结束。现在你需要诚实地评估：
- 对方的论据是否有说服力？
- 你的立场是否需要改变？
- 哪个 Agent 的发言最有影响力？

注意：改变立场不丢人，被好的论据说服是理性的表现。
但如果你仍然坚信自己的立场，也完全没问题。

输出 JSON：
{{
  "change_position": true 或 false,
  "reasoning": "你为什么要/不要改变立场",
  "influenced_by": "如果改变立场，是谁说服了你？如果没改变则为 null"
}}
"""
            result = await self._call_llm(personality, prompt)

            if result.get("change_position", False):
                new_position = Position.NO if current_position == Position.YES else Position.YES
                change = PositionChange(
                    agent_name=personality.name,
                    agent_emoji=personality.emoji,
                    old_position=current_position,
                    new_position=new_position,
                    reasoning=result.get("reasoning", ""),
                    influenced_by=result.get("influenced_by"),
                )
                self.position_changes.append(change)

                # Update the bet record
                for bet in self.bets:
                    if bet.agent_name == personality.name:
                        bet.position = new_position
                        break

                await self._emit("position_change", {
                    "agent_name": personality.name,
                    "agent_emoji": personality.emoji,
                    "old_position": current_position.value,
                    "new_position": new_position.value,
                    "reasoning": result.get("reasoning", ""),
                    "influenced_by": result.get("influenced_by"),
                })

    # ── Phase 6: Resolution ─────────────────────────────

    async def _resolution_phase(self) -> DebateResult:
        """Judge evaluates and declares winner."""
        self.phase = DebatePhase.RESOLUTION
        await self._emit("phase_change", {
            "phase": "resolution",
            "label": "裁判裁决",
        })

        # Import judge
        from debate.moderator import JudgeAgent
        judge = JudgeAgent(self.api_key)

        ruling = await judge.evaluate(
            topic=self.topic,
            bets=self.bets,
            messages=self.messages,
            position_changes=self.position_changes,
        )

        winning_position = Position.YES if ruling["winning_position"] == "YES" else Position.NO

        # Calculate payouts
        total_pool = sum(bet.stake for bet in self.bets)
        winners = [b for b in self.bets if b.position == winning_position]
        losers = [b for b in self.bets if b.position != winning_position]
        loser_pool = sum(b.stake for b in losers)

        payouts = {}
        for bet in self.bets:
            if bet.position == winning_position:
                # Winners split the loser pool proportionally
                if winners:
                    share = bet.stake / sum(w.stake for w in winners)
                    payouts[bet.agent_name] = round(loser_pool * share, 1)
                else:
                    payouts[bet.agent_name] = 0
            else:
                payouts[bet.agent_name] = round(-bet.stake, 1)

        yes_count = sum(1 for b in self.bets if b.position == Position.YES)
        no_count = sum(1 for b in self.bets if b.position == Position.NO)

        self.phase = DebatePhase.SETTLED
        result = DebateResult(
            topic=self.topic,
            winning_position=winning_position,
            resolution_method=ruling.get("method", "judge_ruling"),
            judge_reasoning=ruling.get("reasoning", ""),
            bets=self.bets,
            messages=self.messages,
            position_changes=self.position_changes,
            payouts=payouts,
            total_pool=total_pool,
            yes_count=yes_count,
            no_count=no_count,
        )

        await self._emit("result", {
            "winning_position": winning_position.value,
            "resolution_method": result.resolution_method,
            "judge_reasoning": result.judge_reasoning,
            "payouts": payouts,
            "total_pool": total_pool,
            "yes_count": yes_count,
            "no_count": no_count,
            "position_changes_count": len(self.position_changes),
        })

        return result

    # ── Helpers ──────────────────────────────────────────

    def _get_position(self, agent_name: str) -> Position | None:
        for bet in self.bets:
            if bet.agent_name == agent_name:
                return bet.position
        return None

    def _format_bets(self, exclude: str = "") -> str:
        lines = []
        for bet in self.bets:
            if bet.agent_name == exclude:
                continue
            side = "支持" if bet.position == Position.YES else "反对"
            lines.append(
                f"  {bet.agent_emoji} {bet.agent_name}：{side} "
                f"(投注 {bet.stake} 积分，信心 {bet.confidence:.0%})"
            )
        return "\n".join(lines) if lines else "（还没有其他人下注）"

    def _format_debate_history(self) -> str:
        if not self.messages:
            return ""
        lines = []
        current_phase = None
        phase_names = {
            DebatePhase.OPENING: "== 第一轮：开场陈述 ==",
            DebatePhase.REBUTTAL: "== 第二轮：反驳交锋 ==",
            DebatePhase.FREE_DEBATE: "== 第三轮：自由辩论 ==",
        }
        for msg in self.messages:
            if msg.phase != current_phase:
                current_phase = msg.phase
                if current_phase in phase_names:
                    lines.append(f"\n{phase_names[current_phase]}")
            side = "支持" if msg.position == Position.YES else "反对"
            target = f" → @{msg.target_agent}" if msg.target_agent else ""
            lines.append(f"{msg.agent_emoji} {msg.agent_name}（{side}）{target}：{msg.content}")
        return "\n".join(lines)

    async def _call_llm(self, personality: AgentPersonality, prompt: str) -> dict:
        """Call Claude with the agent's personality."""
        debate_system = (
            f"{personality.system_prompt}\n\n"
            f"你现在正在参加一场辩论赛。请保持你的性格特点（{personality.description}），"
            f"但要认真对待辩论，用有说服力的论据来支持你的立场。"
            f"注意：你必须只输出 JSON，不要有其他文字。"
        )

        try:
            response = await self.llm.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                system=debate_system,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            print(f"[DebateRoom] LLM error for {personality.name}: {e}")

        # Fallback
        return {
            "position": random.choice(["YES", "NO"]),
            "confidence": 0.5,
            "reasoning": "（思考中...）",
            "content": "我需要更多时间思考这个问题。",
            "change_position": False,
        }
