"""预测交易 Agent — 基于舆情分析做概率推理和模拟交易"""

import uuid
from datetime import datetime

import anthropic

from market.models import (
    AgentPortfolio,
    PredictionMarket,
    SentimentReport,
    Trade,
    TradeDirection,
)


SYSTEM_PROMPT = """\
你是一个预测市场的交易员 Agent。你需要基于舆情分析报告和市场信息，决定是否交易。

你的决策框架：
1. 分析舆情报告中的正反方论据
2. 评估当前市场概率是否合理
3. 如果你认为真实概率与市场概率有显著偏差（>10%），考虑交易
4. 使用 Kelly criterion 计算仓位大小
5. 给出你的推理过程

Kelly fraction = (bp - q) / b
其中 b = 赔率, p = 你估计的胜率, q = 1 - p

输出 JSON 格式：
{
  "should_trade": true|false,
  "direction": "buy_yes"|"buy_no",
  "estimated_probability": 0.0-1.0,
  "confidence": 0.0-1.0,
  "kelly_fraction": 0.0-1.0,
  "suggested_amount": 金额,
  "reasoning": "详细推理过程"
}
"""


class PredictionTraderAgent:
    """基于舆情分析做概率推理和交易"""

    def __init__(self, anthropic_api_key: str):
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.portfolio = AgentPortfolio(agent_name="prediction_trader")

    async def evaluate_and_trade(
        self, market: PredictionMarket, sentiment: SentimentReport
    ) -> Trade | None:
        """评估市场并决定是否交易"""
        market_info = (
            f"预测命题：{market.title}\n"
            f"描述：{market.description}\n"
            f"当前 YES 概率：{market.yes_probability}\n"
            f"分类：{market.category}\n"
            f"结算日期：{market.resolution_date}\n"
        )

        sentiment_info = (
            f"舆情分析结果：\n"
            f"  正面比例：{sentiment.positive_ratio}\n"
            f"  负面比例：{sentiment.negative_ratio}\n"
            f"  中性比例：{sentiment.neutral_ratio}\n"
            f"  置信度：{sentiment.confidence}\n"
            f"  趋势：{sentiment.sentiment_trend}\n"
            f"  正方论据：{'; '.join(sentiment.key_arguments_for)}\n"
            f"  反方论据：{'; '.join(sentiment.key_arguments_against)}\n"
            f"  专家观点：{'; '.join(sentiment.top_expert_opinions)}\n"
        )

        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"当前账户余额：{self.portfolio.balance}\n\n"
                    f"{market_info}\n\n{sentiment_info}\n\n"
                    f"请分析并决定是否交易。"
                ),
            }],
        )

        import json
        content = response.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        data = json.loads(content[start:end])

        if not data.get("should_trade", False):
            return None

        direction = (
            TradeDirection.BUY_YES
            if data["direction"] == "buy_yes"
            else TradeDirection.BUY_NO
        )
        amount = min(data.get("suggested_amount", 10), self.portfolio.balance * 0.1)

        trade = Trade(
            id=str(uuid.uuid4())[:8],
            market_id=market.id,
            agent_name=self.portfolio.agent_name,
            direction=direction,
            amount=amount,
            probability_at_trade=market.yes_probability,
            reasoning=data.get("reasoning", ""),
        )

        # 更新持仓
        self.portfolio.balance -= amount
        self.portfolio.total_trades += 1
        self.portfolio.positions[market.id] = (direction, amount)

        return trade
