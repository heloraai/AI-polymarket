"""预测市场数据模型 — Agent 对战版

核心概念：多个 AI Agent 在同一个预测市场里互相博弈。
市场价格不是预设的，而是由 Agent 的交易行为决定的。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MarketStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED_YES = "resolved_yes"
    RESOLVED_NO = "resolved_no"


class TradeDirection(Enum):
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"


@dataclass
class PredictionMarket:
    """一个预测市场"""
    id: str
    title: str                          # 预测命题
    description: str
    source_question_id: str             # 来源知乎问题 ID
    source_question_title: str
    category: str
    created_at: datetime = field(default_factory=datetime.now)
    resolution_date: datetime | None = None
    status: MarketStatus = MarketStatus.OPEN
    yes_probability: float = 0.5        # 当前 YES 概率（由交易驱动）
    total_volume: float = 0.0


@dataclass
class Trade:
    """一笔交易"""
    id: str
    market_id: str
    agent_name: str
    direction: TradeDirection
    amount: float
    probability_at_trade: float
    confidence: float                   # Agent 对自己判断的信心
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentPortfolio:
    """Agent 的持仓和绩效"""
    agent_name: str
    personality: str = ""               # 性格标签
    balance: float = 1000.0
    total_trades: int = 0
    winning_trades: int = 0
    pnl: float = 0.0                    # 累计盈亏
    positions: dict = field(default_factory=dict)  # market_id -> list[Trade]

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades


@dataclass
class SentimentReport:
    """知乎舆情分析报告"""
    question_id: str
    question_title: str
    total_answers_analyzed: int
    positive_ratio: float
    negative_ratio: float
    neutral_ratio: float
    confidence: float
    key_arguments_for: list[str] = field(default_factory=list)
    key_arguments_against: list[str] = field(default_factory=list)
    top_expert_opinions: list[str] = field(default_factory=list)
    sentiment_trend: str = "stable"


@dataclass
class ArenaResult:
    """一轮竞技场的结果"""
    market: PredictionMarket
    trades: list[Trade]
    leaderboard: list[AgentPortfolio]   # 按盈亏排序
    price_history: list[float]          # 概率变化轨迹
