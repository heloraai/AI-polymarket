"""辩论室 — Agent 观点擂台的核心引擎（Polymarket 多选项版）

流程：
1. 选题：从知乎热榜选取话题，提供 2-4 个观点选项
2. 下注：Agent 选择一个立场，根据信心动态下注
3. 辩论：3轮（开场陈述 → 反驳 → 自由辩论）
4. 立场更新：辩论后 Agent 可以被说服改变立场
5. 裁决：裁判综合证据 + 逻辑 + 说服效果判定胜出选项
6. 结算：赢方按 Polymarket 份额机制瓜分积分池
"""

import json
import random
from typing import Callable, Optional

import anthropic

from agents.personalities import AgentPersonality, ALL_PERSONALITIES
from debate.models import (
    AgentBet, DebateEvent, DebateMessage, DebatePhase,
    DebateResult, DebateTopic, MarketState,
    PositionChange, PositionOption,
)


class DebateRoom:
    """辩论室：管理一场多选项辩论"""

    def __init__(
        self,
        topic: DebateTopic,
        personalities: list[AgentPersonality] | None = None,
        anthropic_api_key: str = "",
        base_stake: float = 100.0,
    ):
        self.topic = topic
        self.personalities = personalities or ALL_PERSONALITIES
        self.api_key = anthropic_api_key
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.base_stake = base_stake

        # Build option lookup
        self.options = {opt.key: opt for opt in topic.options}

        # State
        self.phase = DebatePhase.WAITING
        self.bets: list[AgentBet] = []
        self.messages: list[DebateMessage] = []
        self.position_changes: list[PositionChange] = []
        self.events: list[DebateEvent] = []

        # Market state (Polymarket-style)
        self.market = MarketState(
            option_pools={opt.key: 0.0 for opt in topic.options},
            option_shares={opt.key: 0 for opt in topic.options},
        )

        self._event_callback: Optional[Callable] = None

    def on_event(self, callback: Callable):
        self._event_callback = callback

    async def _emit(self, event_type: str, data: dict):
        event = DebateEvent(type=event_type, phase=self.phase, data=data)
        self.events.append(event)
        if self._event_callback:
            await self._event_callback(event)

    async def run(self) -> DebateResult:
        """Run the full multi-option debate flow."""
        await self._betting_phase()
        await self._debate_round(1, DebatePhase.OPENING)
        await self._debate_round(2, DebatePhase.REBUTTAL)
        await self._debate_round(3, DebatePhase.FREE_DEBATE)
        await self._position_update_phase()
        return await self._resolution_phase()

    # ── Phase 1: Betting ─────────────────────────────────

    async def _betting_phase(self):
        self.phase = DebatePhase.BETTING
        await self._emit("phase_change", {"phase": "betting", "label": "下注阶段"})

        agents = list(self.personalities)
        random.shuffle(agents)

        options_text = "\n".join(
            f"  {i+1}. [{opt.key}] {opt.label} — {opt.description}"
            for i, opt in enumerate(self.topic.options)
        )

        for personality in agents:
            decision = await self._agent_bet(personality, options_text)

            # Validate option key
            chosen_key = decision.get("position", "")
            if chosen_key not in self.options:
                # Fuzzy match: try label matching
                for opt in self.topic.options:
                    if opt.label in chosen_key or chosen_key in opt.label:
                        chosen_key = opt.key
                        break
                else:
                    chosen_key = self.topic.options[0].key

            option = self.options[chosen_key]
            confidence = min(max(decision.get("confidence", 0.5), 0.1), 1.0)

            # Dynamic stake: base × confidence × risk_appetite
            stake = round(
                self.base_stake * confidence * personality.risk_appetite, 1
            )
            stake = max(10.0, stake)  # Minimum bet

            # Update market state
            self.market.option_pools[chosen_key] += stake
            self.market.option_shares[chosen_key] += 1
            self.market.total_pool += stake

            odds_at_bet = self.market.get_price(chosen_key)
            payout_mult = self.market.get_payout_multiplier(chosen_key)

            bet = AgentBet(
                agent_name=personality.name,
                agent_emoji=personality.emoji,
                position=chosen_key,
                position_label=option.label,
                stake=stake,
                confidence=confidence,
                reasoning=decision.get("reasoning", ""),
                odds_at_bet=odds_at_bet,
                potential_payout=round(stake * payout_mult, 1),
            )
            self.bets.append(bet)

            await self._emit("bet", {
                "agent_name": personality.name,
                "agent_emoji": personality.emoji,
                "position": chosen_key,
                "position_label": option.label,
                "position_color": option.color,
                "stake": stake,
                "confidence": confidence,
                "reasoning": decision.get("reasoning", ""),
                "odds": odds_at_bet,
                "potential_payout": bet.potential_payout,
            })

            # Emit market update after each bet
            await self._emit("market_update", {
                "odds": self.market.get_odds(),
                "pools": self.market.option_pools,
                "shares": self.market.option_shares,
                "total_pool": self.market.total_pool,
            })

    async def _agent_bet(self, personality: AgentPersonality, options_text: str) -> dict:
        prompt = f"""\
你正在参加一场辩论赛。辩题：

「{self.topic.title}」

背景信息：
{self.topic.context}

可选立场：
{options_text}

你需要选择一个立场，并准备为它辩护。
你的赌注金额将根据你的信心自动计算（信心越高，赌注越大）。

当前市场赔率：
{self._format_market_odds()}

根据你的性格特点（{personality.description}），选择你认为最正确的立场。

输出 JSON：
{{
  "position": "选项的key（如 {self.topic.options[0].key}）",
  "confidence": 0.1-1.0,
  "reasoning": "你选择这个立场的原因（一句话）"
}}
"""
        return await self._call_llm(personality, prompt)

    # ── Phase 2-4: Debate Rounds ─────────────────────────

    async def _debate_round(self, round_num: int, phase: DebatePhase):
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

        # Group agents by position, interleave for drama
        position_groups: dict[str, list[AgentPersonality]] = {}
        for p in self.personalities:
            pos = self._get_position(p.name)
            if pos:
                position_groups.setdefault(pos, []).append(p)

        for group in position_groups.values():
            random.shuffle(group)

        # Round-robin interleave across position groups
        speaking_order = []
        group_lists = list(position_groups.values())
        max_len = max((len(g) for g in group_lists), default=0)
        for i in range(max_len):
            for group in group_lists:
                if i < len(group):
                    speaking_order.append(group[i])

        for personality in speaking_order:
            message = await self._agent_speak(personality, round_num, phase)
            if message:
                self.messages.append(message)
                await self._emit("message", {
                    "id": message.id,
                    "agent_name": message.agent_name,
                    "agent_emoji": message.agent_emoji,
                    "position": message.position,
                    "position_label": message.position_label,
                    "content": message.content,
                    "round_num": round_num,
                    "phase": phase.value,
                    "target_agent": message.target_agent,
                    "tactics": message.persuasion_tactics,
                })

    async def _agent_speak(
        self, personality: AgentPersonality, round_num: int, phase: DebatePhase
    ) -> DebateMessage | None:
        position_key = self._get_position(personality.name)
        if not position_key or position_key not in self.options:
            return None
        option = self.options[position_key]

        debate_history = self._format_debate_history()
        bets_summary = self._format_bets(exclude=personality.name)
        market_odds = self._format_market_odds()

        phase_instructions = {
            DebatePhase.OPENING: (
                "这是开场陈述阶段。请清晰阐述你的立场和核心论据。"
                "要有气势，要让持其他观点的人知道你不好惹。"
                "限制在 2-3 个核心论点内。"
            ),
            DebatePhase.REBUTTAL: (
                "这是反驳阶段。你需要：\n"
                "1. 针对其他阵营的核心论据进行反驳\n"
                "2. 指出对方逻辑中的漏洞\n"
                "3. 用数据或案例加强自己的论点\n"
                "你可以点名反驳某个特定的 Agent。要犀利但有理有据。"
            ),
            DebatePhase.FREE_DEBATE: (
                "这是自由辩论阶段，最后的交锋机会！你可以：\n"
                "1. 发起新的攻击角度\n"
                "2. 总结性地摧毁对方的论点\n"
                "3. 尝试说服其他阵营中立场不坚定的 Agent 改投你的阵营\n"
                "4. 做出有力的总结陈词\n"
                "这是你最后的机会，全力以赴！"
            ),
        }

        prompt = f"""\
辩题：「{self.topic.title}」

背景信息：
{self.topic.context}

你的立场：{option.label}（{option.description}）

当前市场赔率：
{market_odds}

其他 Agent 的下注情况：
{bets_summary}

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
  "tactics": ["使用的辩论策略，如：数据论证、类比论证、归谬法、情感诉求"]
}}
"""
        result = await self._call_llm(personality, prompt)

        return DebateMessage(
            agent_name=personality.name,
            agent_emoji=personality.emoji,
            position=position_key,
            position_label=option.label,
            content=result.get("content", "..."),
            round_num=round_num,
            phase=phase,
            target_agent=result.get("target_agent"),
            persuasion_tactics=result.get("tactics", []),
        )

    # ── Phase 5: Position Update ────────────────────────

    async def _position_update_phase(self):
        self.phase = DebatePhase.POSITION_UPDATE
        await self._emit("phase_change", {"phase": "position_update", "label": "立场更新"})

        debate_history = self._format_debate_history()
        options_text = "\n".join(
            f"  [{opt.key}] {opt.label}"
            for opt in self.topic.options
        )

        for personality in self.personalities:
            current_key = self._get_position(personality.name)
            if not current_key or current_key not in self.options:
                continue
            current_option = self.options[current_key]

            prompt = f"""\
辩题：「{self.topic.title}」

你的当前立场：{current_option.label}

所有可选立场：
{options_text}

完整辩论记录：
{debate_history}

辩论已经结束。现在你需要诚实地评估：
- 其他阵营的论据是否有说服力？
- 你是否需要改变立场？
- 哪个 Agent 的发言最有影响力？

注意：改变立场不丢人。但如果仍然坚信自己的立场，也完全没问题。

输出 JSON：
{{
  "change_position": true 或 false,
  "new_position": "如果改变，填新立场的key；如果不改变，填当前立场的key",
  "reasoning": "为什么要/不要改变",
  "influenced_by": "如果改变，是谁说服了你？没有则为 null"
}}
"""
            result = await self._call_llm(personality, prompt)

            if result.get("change_position", False):
                new_key = result.get("new_position", current_key)
                if new_key in self.options and new_key != current_key:
                    new_option = self.options[new_key]
                    change = PositionChange(
                        agent_name=personality.name,
                        agent_emoji=personality.emoji,
                        old_position=current_key,
                        old_label=current_option.label,
                        new_position=new_key,
                        new_label=new_option.label,
                        reasoning=result.get("reasoning", ""),
                        influenced_by=result.get("influenced_by"),
                    )
                    self.position_changes.append(change)

                    # Update bet record and market state
                    for bet in self.bets:
                        if bet.agent_name == personality.name:
                            # Move stake from old to new pool
                            self.market.option_pools[current_key] -= bet.stake
                            self.market.option_shares[current_key] -= 1
                            self.market.option_pools[new_key] += bet.stake
                            self.market.option_shares[new_key] += 1
                            bet.position = new_key
                            bet.position_label = new_option.label
                            break

                    await self._emit("position_change", {
                        "agent_name": personality.name,
                        "agent_emoji": personality.emoji,
                        "old_position": current_key,
                        "old_label": current_option.label,
                        "new_position": new_key,
                        "new_label": new_option.label,
                        "reasoning": result.get("reasoning", ""),
                        "influenced_by": result.get("influenced_by"),
                    })
                    await self._emit("market_update", {
                        "odds": self.market.get_odds(),
                        "pools": self.market.option_pools,
                        "shares": self.market.option_shares,
                        "total_pool": self.market.total_pool,
                    })

    # ── Phase 6: Resolution ─────────────────────────────

    async def _resolution_phase(self) -> DebateResult:
        self.phase = DebatePhase.RESOLUTION
        await self._emit("phase_change", {"phase": "resolution", "label": "裁判裁决"})

        from debate.moderator import JudgeAgent
        judge = JudgeAgent(self.api_key)

        ruling = await judge.evaluate(
            topic=self.topic,
            bets=self.bets,
            messages=self.messages,
            position_changes=self.position_changes,
        )

        winning_key = ruling.get("winning_position", "")
        if winning_key not in self.options:
            # Fallback: option with most bets
            counts = {}
            for b in self.bets:
                counts[b.position] = counts.get(b.position, 0) + 1
            winning_key = max(counts, key=counts.get) if counts else self.topic.options[0].key

        winning_option = self.options[winning_key]

        # Calculate payouts (Polymarket-style: winners split $1 per share)
        winners = [b for b in self.bets if b.position == winning_key]
        losers = [b for b in self.bets if b.position != winning_key]
        loser_pool = sum(b.stake for b in losers)

        payouts = {}
        for bet in self.bets:
            if bet.position == winning_key:
                if winners:
                    share = bet.stake / sum(w.stake for w in winners)
                    payouts[bet.agent_name] = round(loser_pool * share, 1)
                else:
                    payouts[bet.agent_name] = 0
            else:
                payouts[bet.agent_name] = round(-bet.stake, 1)

        option_counts = {}
        for b in self.bets:
            option_counts[b.position] = option_counts.get(b.position, 0) + 1

        self.phase = DebatePhase.SETTLED
        result = DebateResult(
            topic=self.topic,
            winning_position=winning_key,
            winning_label=winning_option.label,
            resolution_method=ruling.get("method", "judge_ruling"),
            judge_reasoning=ruling.get("reasoning", ""),
            scores=ruling.get("scores", {}),
            mvp=ruling.get("mvp", ""),
            highlights=ruling.get("highlights", []),
            bets=self.bets,
            messages=self.messages,
            position_changes=self.position_changes,
            payouts=payouts,
            total_pool=self.market.total_pool,
            market_state=self.market,
            option_counts=option_counts,
        )

        await self._emit("result", {
            "winning_position": winning_key,
            "winning_label": winning_option.label,
            "winning_color": winning_option.color,
            "resolution_method": result.resolution_method,
            "judge_reasoning": result.judge_reasoning,
            "scores": result.scores,
            "mvp": result.mvp,
            "highlights": result.highlights,
            "payouts": payouts,
            "total_pool": self.market.total_pool,
            "option_counts": option_counts,
            "position_changes_count": len(self.position_changes),
            "final_odds": self.market.get_odds(),
        })

        return result

    # ── Helpers ──────────────────────────────────────────

    def _get_position(self, agent_name: str) -> str | None:
        for bet in self.bets:
            if bet.agent_name == agent_name:
                return bet.position
        return None

    def _get_label(self, option_key: str) -> str:
        opt = self.options.get(option_key)
        return opt.label if opt else option_key

    def _format_market_odds(self) -> str:
        odds = self.market.get_odds()
        if not odds or self.market.total_pool == 0:
            n = len(self.topic.options)
            return "\n".join(
                f"  {opt.label}: ${1/n:.2f} (均等)"
                for opt in self.topic.options
            )
        lines = []
        for opt in self.topic.options:
            p = odds.get(opt.key, 0)
            mult = self.market.get_payout_multiplier(opt.key)
            pool = self.market.option_pools.get(opt.key, 0)
            lines.append(
                f"  {opt.label}: ${p:.2f} (赔率 {mult:.1f}x | 池内 {pool:.0f}分)"
            )
        return "\n".join(lines)

    def _format_bets(self, exclude: str = "") -> str:
        lines = []
        for bet in self.bets:
            if bet.agent_name == exclude:
                continue
            lines.append(
                f"  {bet.agent_emoji} {bet.agent_name}：{bet.position_label} "
                f"(投注 {bet.stake:.0f}分，信心 {bet.confidence:.0%})"
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
            target = f" → @{msg.target_agent}" if msg.target_agent else ""
            lines.append(
                f"{msg.agent_emoji} {msg.agent_name}（{msg.position_label}）{target}：{msg.content}"
            )
        return "\n".join(lines)

    async def _call_llm(self, personality: AgentPersonality, prompt: str) -> dict:
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
        default_key = self.topic.options[0].key if self.topic.options else ""
        return {
            "position": random.choice([o.key for o in self.topic.options]) if self.topic.options else default_key,
            "confidence": 0.5,
            "reasoning": "（思考中...）",
            "content": "我需要更多时间思考这个问题。",
            "change_position": False,
            "new_position": default_key,
        }
