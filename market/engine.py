"""市场引擎 — 用 Agent 的交易行为驱动市场价格

简化的 LMSR（对数市场评分规则）做市商：
- 任何 Agent 都可以随时买 YES 或 NO
- 每笔交易都会移动市场价格
- 买 YES 的人多 → 价格上升，买 NO 的人多 → 价格下降
- 结算时：YES 方或 NO 方赢得对方的赌注

这比简单的"每个 Agent 独立输出概率"有趣得多——
Agent 的交易互相影响，形成真正的博弈。
"""

import math
from .models import PredictionMarket, Trade, TradeDirection


class MarketEngine:
    """LMSR 做市商引擎

    用 b 参数控制市场深度（流动性）。
    b 越大，单笔交易对价格的影响越小。
    """

    def __init__(self, b: float = 100.0):
        self.b = b
        # 内部状态：YES 和 NO 的虚拟持仓量
        self._yes_shares: dict[str, float] = {}  # market_id -> shares
        self._no_shares: dict[str, float] = {}

    def init_market(self, market: PredictionMarket):
        """初始化市场，设定初始均衡"""
        self._yes_shares[market.id] = 0.0
        self._no_shares[market.id] = 0.0

    def get_price(self, market_id: str) -> float:
        """获取当前 YES 价格 (0-1)"""
        yes_q = self._yes_shares.get(market_id, 0.0)
        no_q = self._no_shares.get(market_id, 0.0)
        # LMSR 价格公式
        return math.exp(yes_q / self.b) / (
            math.exp(yes_q / self.b) + math.exp(no_q / self.b)
        )

    def execute_trade(self, market: PredictionMarket, trade: Trade) -> float:
        """执行交易，返回交易后的新价格

        交易成本由 LMSR 自动计算：
        买入越多，边际成本越高（防止单个 Agent 操纵价格）。
        """
        if trade.direction == TradeDirection.BUY_YES:
            self._yes_shares[market.id] = (
                self._yes_shares.get(market.id, 0.0) + trade.amount
            )
        else:
            self._no_shares[market.id] = (
                self._no_shares.get(market.id, 0.0) + trade.amount
            )

        new_price = self.get_price(market.id)
        market.yes_probability = new_price
        market.total_volume += trade.amount
        return new_price

    def settle(
        self,
        market: PredictionMarket,
        trades: list[Trade],
        outcome_yes: bool,
    ) -> dict[str, float]:
        """结算市场，计算每个 Agent 的盈亏

        赢家：获得 amount * (1/price_at_trade - 1) 的利润
        输家：损失全部 amount
        零和博弈 — 赢家的利润来自输家的损失。

        Returns: {agent_name: pnl}
        """
        pnl: dict[str, float] = {}

        for trade in trades:
            name = trade.agent_name
            if name not in pnl:
                pnl[name] = 0.0

            is_winner = (
                (outcome_yes and trade.direction == TradeDirection.BUY_YES)
                or (not outcome_yes and trade.direction == TradeDirection.BUY_NO)
            )

            if is_winner:
                # 赢家按买入时的赔率获利
                price = trade.probability_at_trade
                if trade.direction == TradeDirection.BUY_NO:
                    price = 1.0 - price
                profit = trade.amount * (1.0 / max(price, 0.01) - 1.0)
                pnl[name] += profit
            else:
                pnl[name] -= trade.amount

        return pnl
