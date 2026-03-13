"""竞技场 — 多 Agent 对战的核心编排器

流程：
1. TopicHunter 从知乎热榜发现预测市场
2. 每个市场：所有 Agent 看到同样的知乎数据
3. 每个 Agent 根据自己的性格独立做出交易决策
4. 交易通过 LMSR 引擎执行，每笔交易都会移动市场价格
5. 后续 Agent 看到前面 Agent 交易后的价格变化
6. 所有 Agent 交易完毕后，展示结果

关键设计：Agent 的交易顺序会影响结果（先手优势），
所以每轮随机打乱顺序，确保公平。
"""

import json
import random
import uuid

import anthropic

from zhihu.client import ZhihuClient, _strip_html
from market.models import (
    AgentPortfolio, ArenaResult, PredictionMarket,
    Trade, TradeDirection,
)
from market.engine import MarketEngine
from .personalities import AgentPersonality, ALL_PERSONALITIES


class Arena:
    """AI Agent 对战竞技场"""

    def __init__(
        self,
        zhihu_client: ZhihuClient,
        anthropic_api_key: str,
        personalities: list[AgentPersonality] | None = None,
    ):
        self.zhihu = zhihu_client
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.engine = MarketEngine(b=100.0)
        self.personalities = personalities or ALL_PERSONALITIES

        # 每个 Agent 一个 portfolio
        self.portfolios: dict[str, AgentPortfolio] = {}
        for p in self.personalities:
            self.portfolios[p.name] = AgentPortfolio(
                agent_name=p.name,
                personality=p.description,
            )

    async def run_market(self, market: PredictionMarket) -> ArenaResult:
        """在一个预测市场上进行一轮完整的 Agent 对战"""
        self.engine.init_market(market)
        price_history = [market.yes_probability]

        # 获取知乎数据（所有 Agent 看到的信息一样）
        zhihu_data = await self._gather_zhihu_data(market.source_question_id)

        # 随机打乱 Agent 顺序（避免固定的先手优势）
        agents_order = list(self.personalities)
        random.shuffle(agents_order)

        all_trades: list[Trade] = []
        trade_log: list[str] = []  # 给后续 Agent 看的交易记录

        for personality in agents_order:
            portfolio = self.portfolios[personality.name]
            if portfolio.balance <= 0:
                continue

            # 构建给当前 Agent 的信息（包含前面 Agent 的交易记录）
            trade_context = ""
            if trade_log:
                trade_context = (
                    "\n\n--- 其他 Agent 的交易记录（你可以参考，也可以忽略）---\n"
                    + "\n".join(trade_log)
                )

            current_price = self.engine.get_price(market.id)
            decision = await self._agent_decide(
                personality=personality,
                market=market,
                zhihu_data=zhihu_data,
                current_price=current_price,
                portfolio=portfolio,
                trade_context=trade_context,
            )

            if decision and decision["direction"] != "skip":
                trade = self._create_trade(
                    personality, market, decision, portfolio, current_price
                )
                if trade:
                    new_price = self.engine.execute_trade(market, trade)
                    all_trades.append(trade)
                    price_history.append(new_price)

                    # 记录交易供后续 Agent 参考
                    trade_log.append(
                        f"  {personality.emoji} {personality.name}: "
                        f"{trade.direction.value} ${trade.amount:.0f} "
                        f"(价格 {current_price:.0%} → {new_price:.0%})"
                    )

        # 排行榜（按当前余额排序）
        leaderboard = sorted(
            self.portfolios.values(),
            key=lambda p: p.balance,
            reverse=True,
        )

        return ArenaResult(
            market=market,
            trades=all_trades,
            leaderboard=list(leaderboard),
            price_history=price_history,
        )

    def settle_market(
        self, market: PredictionMarket, trades: list[Trade], outcome_yes: bool
    ):
        """结算市场，更新所有 Agent 的盈亏"""
        pnl = self.engine.settle(market, trades, outcome_yes)

        for agent_name, profit in pnl.items():
            portfolio = self.portfolios[agent_name]
            portfolio.balance += profit
            portfolio.pnl += profit

            # 统计胜率
            agent_trades = [t for t in trades if t.agent_name == agent_name]
            for t in agent_trades:
                portfolio.total_trades += 1
                is_win = (
                    (outcome_yes and t.direction == TradeDirection.BUY_YES)
                    or (not outcome_yes and t.direction == TradeDirection.BUY_NO)
                )
                if is_win:
                    portfolio.winning_trades += 1

    async def _gather_zhihu_data(self, question_id: str) -> str:
        """采集知乎数据，格式化为所有 Agent 共享的信息文本"""
        question = await self.zhihu.get_question(question_id)
        answers = await self.zhihu.get_answers(question_id, limit=15)

        lines = [
            f"知乎问题：{question.title}",
            f"关注人数：{question.follower_count} | 回答数：{question.answer_count}",
            "",
        ]

        for a in answers:
            author_info = a.author_name
            if a.author_headline:
                author_info += f" ({a.author_headline})"
            content = _strip_html(a.content)[:1000]
            lines.append(
                f"--- {author_info} | 赞同: {a.voteup_count} ---\n{content}\n"
            )

        return "\n".join(lines)

    async def _agent_decide(
        self,
        personality: AgentPersonality,
        market: PredictionMarket,
        zhihu_data: str,
        current_price: float,
        portfolio: AgentPortfolio,
        trade_context: str,
    ) -> dict | None:
        """让一个 Agent 做出交易决策"""

        user_prompt = (
            f"预测命题：{market.title}\n"
            f"描述：{market.description}\n"
            f"分类：{market.category}\n"
            f"当前市场 YES 价格：{current_price:.0%}\n"
            f"你的账户余额：{portfolio.balance:.0f}\n"
            f"\n"
            f"以下是知乎上关于这个话题的讨论：\n\n"
            f"{zhihu_data}"
            f"{trade_context}\n\n"
            f"请做出你的交易决策。"
        )

        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=personality.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            return None

    def _create_trade(
        self,
        personality: AgentPersonality,
        market: PredictionMarket,
        decision: dict,
        portfolio: AgentPortfolio,
        current_price: float,
    ) -> Trade | None:
        """根据 Agent 的决策创建交易"""
        direction_str = decision.get("direction", "skip")
        if direction_str == "skip":
            return None

        direction = (
            TradeDirection.BUY_YES if direction_str == "buy_yes"
            else TradeDirection.BUY_NO
        )

        # 根据 Agent 性格和决策计算下注金额
        bet_fraction = min(
            decision.get("bet_fraction", 0.05),
            personality.risk_appetite * 0.3,  # 上限 = 风险偏好 × 30%
        )
        amount = portfolio.balance * max(bet_fraction, 0.01)
        amount = min(amount, portfolio.balance)  # 不能超过余额

        if amount < 1:
            return None

        # 扣除余额
        portfolio.balance -= amount

        # 记录持仓
        if market.id not in portfolio.positions:
            portfolio.positions[market.id] = []
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            market_id=market.id,
            agent_name=personality.name,
            direction=direction,
            amount=amount,
            probability_at_trade=current_price,
            confidence=decision.get("confidence", 0.5),
            reasoning=decision.get("reasoning", ""),
        )
        portfolio.positions[market.id].append(trade)
        return trade
