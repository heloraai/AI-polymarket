"""Data models for the debate arena system.

Polymarket-inspired multi-option prediction market + debate arena.
Each topic has 2-4 position options (not just YES/NO).
Agents pick positions, place variable stakes, and debate to win.
"""

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class DebatePhase(str, Enum):
    WAITING = "waiting"
    BETTING = "betting"
    OPENING = "opening"
    REBUTTAL = "rebuttal"
    FREE_DEBATE = "free_debate"
    POSITION_UPDATE = "position_update"
    RESOLUTION = "resolution"
    SETTLED = "settled"


class PositionOption(BaseModel):
    """A selectable position/outcome for a debate topic (Polymarket-style)."""
    key: str              # Short key, e.g. "replace_fully"
    label: str            # Display name, e.g. "完全取代"
    description: str = "" # Brief description
    color: str = ""       # CSS color for UI


class DebateTopic(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str            # The debate proposition
    options: list[PositionOption] = Field(default_factory=list)  # 2-4 selectable positions
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    category: str = "general"
    context: str = ""     # Background info from Zhihu
    hot_score: float = 0.0


class MarketState(BaseModel):
    """Real-time market state for a debate (Polymarket-style odds)."""
    option_pools: dict[str, float] = Field(default_factory=dict)   # option_key -> total staked
    option_shares: dict[str, int] = Field(default_factory=dict)    # option_key -> number of bets
    total_pool: float = 0.0

    def get_odds(self) -> dict[str, float]:
        """Calculate implied probability for each option (sum = 1.0)."""
        if self.total_pool == 0:
            return {}
        return {
            k: round(v / self.total_pool, 3) if self.total_pool > 0 else 0
            for k, v in self.option_pools.items()
        }

    def get_price(self, option_key: str) -> float:
        """Polymarket-style price: $0.01-$0.99 = probability."""
        odds = self.get_odds()
        p = odds.get(option_key, 0.0)
        return max(0.01, min(0.99, p))

    def get_payout_multiplier(self, option_key: str) -> float:
        """If you bet $1 on this option and win, you get $X back."""
        price = self.get_price(option_key)
        if price <= 0:
            return 0
        return round(1.0 / price, 2)


class AgentBet(BaseModel):
    agent_name: str
    agent_emoji: str
    position: str         # option_key (not just YES/NO anymore)
    position_label: str   # Human readable label
    stake: float          # Variable stake based on confidence
    confidence: float
    reasoning: str
    odds_at_bet: float = 0.0       # Implied probability when bet was placed
    potential_payout: float = 0.0  # What they'd win if correct


class DebateMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent_name: str
    agent_emoji: str
    position: str         # option_key
    position_label: str
    content: str
    round_num: int
    phase: DebatePhase
    timestamp: datetime = Field(default_factory=datetime.now)
    target_agent: Optional[str] = None
    persuasion_tactics: list[str] = Field(default_factory=list)


class PositionChange(BaseModel):
    agent_name: str
    agent_emoji: str
    old_position: str     # option_key
    old_label: str
    new_position: str     # option_key
    new_label: str
    reasoning: str
    influenced_by: Optional[str] = None


class DebateResult(BaseModel):
    topic: DebateTopic
    winning_position: str         # option_key
    winning_label: str
    resolution_method: str        # "evidence" or "judge_ruling"
    judge_reasoning: str
    scores: dict = Field(default_factory=dict)  # Per-option scores from judge
    mvp: str = ""
    highlights: list[str] = Field(default_factory=list)
    bets: list[AgentBet]
    messages: list[DebateMessage]
    position_changes: list[PositionChange]
    payouts: dict[str, float]     # agent_name -> pnl
    total_pool: float
    market_state: MarketState
    option_counts: dict[str, int] = Field(default_factory=dict)  # option_key -> agent count


class DebateEvent(BaseModel):
    """Real-time event pushed to frontend via WebSocket."""
    type: str  # phase_change, bet, message, position_change, market_update, result
    phase: DebatePhase
    data: dict
    timestamp: datetime = Field(default_factory=datetime.now)
