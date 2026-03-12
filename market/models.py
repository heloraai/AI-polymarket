"""预测市场数据模型"""

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
    title: str                          # 预测命题，如 "2026年暑期档票房冠军是否超过50亿？"
    description: str                    # 详细描述
    source_question_id: str             # 来源知乎问题 ID
    source_question_title: str          # 来源知乎问题标题
    category: str                       # 分类：科技/娱乐/政治/经济
    created_at: datetime = field(default_factory=datetime.now)
    resolution_date: datetime | None = None  # 预计结算日期
    status: MarketStatus = MarketStatus.OPEN
    yes_probability: float = 0.5        # 当前 YES 概率
    total_volume: float = 0.0           # 总交易量
    zhihu_sentiment_score: float = 0.0  # 知乎舆情分数 (-1 到 1)


@dataclass
class Trade:
    """一笔交易"""
    id: str
    market_id: str
    agent_name: str                     # 哪个 Agent 下的单
    direction: TradeDirection
    amount: float                       # 下注金额（虚拟积分）
    probability_at_trade: float         # 交易时的概率
    reasoning: str                      # AI 的推理过程
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentPortfolio:
    """Agent 的持仓和绩效"""
    agent_name: str
    balance: float = 1000.0             # 初始虚拟积分
    total_trades: int = 0
    winning_trades: int = 0
    positions: dict = field(default_factory=dict)  # market_id -> (direction, amount)

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
    positive_ratio: float               # 正面观点比例
    negative_ratio: float               # 负面观点比例
    neutral_ratio: float                # 中性观点比例
    confidence: float                   # 分析置信度
    key_arguments_for: list[str] = field(default_factory=list)   # 正方核心论据
    key_arguments_against: list[str] = field(default_factory=list)  # 反方核心论据
    top_expert_opinions: list[str] = field(default_factory=list)   # 高可信度答主观点
    sentiment_trend: str = "stable"     # rising / falling / stable
