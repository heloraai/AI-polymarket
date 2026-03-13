"""结果裁判 Agent — 追踪事件进展，到期后判定结果并结算"""

import anthropic

from market.models import AgentPortfolio, MarketStatus, PredictionMarket, Trade, TradeDirection


SYSTEM_PROMPT = """\
你是一个预测市场的裁判。你的任务是在预测事件到期后，根据可获取的信息判定结果。

判定规则：
1. 搜索最新信息确认事件结果
2. 如果结果明确，判定 YES 或 NO
3. 如果结果尚不明确，标记为 PENDING
4. 给出判定理由

输出 JSON 格式：
{
  "resolution": "yes"|"no"|"pending",
  "confidence": 0.0-1.0,
  "evidence": "判定依据",
  "source": "信息来源"
}
"""


class OutcomeJudgeAgent:
    """判定预测市场结果并结算"""

    def __init__(self, anthropic_api_key: str):
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    async def judge(self, market: PredictionMarket) -> MarketStatus:
        """判定某个预测市场的结果"""
        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"预测命题：{market.title}\n"
                    f"描述：{market.description}\n"
                    f"结算日期：{market.resolution_date}\n"
                    f"来源知乎问题：{market.source_question_title}\n\n"
                    f"请判定结果。"
                ),
            }],
        )

        import json
        content = response.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return MarketStatus.OPEN  # 无法判定，保持 OPEN

        data = json.loads(content[start:end])

        resolution = data.get("resolution", "pending")
        if resolution == "yes":
            return MarketStatus.RESOLVED_YES
        elif resolution == "no":
            return MarketStatus.RESOLVED_NO
        return MarketStatus.OPEN

    def settle(
        self,
        market: PredictionMarket,
        trades: list[Trade],
        portfolios: dict[str, AgentPortfolio],
    ) -> dict[str, float]:
        """结算某个市场的所有交易，返回各 Agent 的盈亏"""
        pnl = {}

        for trade in trades:
            if trade.market_id != market.id:
                continue

            won = (
                (market.status == MarketStatus.RESOLVED_YES and trade.direction == TradeDirection.BUY_YES)
                or (market.status == MarketStatus.RESOLVED_NO and trade.direction == TradeDirection.BUY_NO)
            )

            if won:
                profit = trade.amount * (1.0 / trade.probability_at_trade - 1)
                portfolios[trade.agent_name].balance += trade.amount + profit
                portfolios[trade.agent_name].winning_trades += 1
            else:
                profit = -trade.amount

            pnl[trade.agent_name] = pnl.get(trade.agent_name, 0) + profit

        return pnl
