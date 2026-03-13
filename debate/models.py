"""Data models for the debate arena system."""

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


class Position(str, Enum):
    YES = "YES"
    NO = "NO"


class DebateTopic(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str  # The debate proposition (YES/NO question)
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    category: str = "general"
    context: str = ""  # Background info from Zhihu
    hot_score: float = 0.0


class AgentBet(BaseModel):
    agent_name: str
    agent_emoji: str
    position: Position
    stake: float
    confidence: float
    reasoning: str


class DebateMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent_name: str
    agent_emoji: str
    position: Position
    content: str
    round_num: int
    phase: DebatePhase
    timestamp: datetime = Field(default_factory=datetime.now)
    target_agent: Optional[str] = None  # Who they're responding to
    persuasion_tactics: list[str] = Field(default_factory=list)


class PositionChange(BaseModel):
    agent_name: str
    agent_emoji: str
    old_position: Position
    new_position: Position
    reasoning: str
    influenced_by: Optional[str] = None  # Which agent persuaded them


class DebateResult(BaseModel):
    topic: DebateTopic
    winning_position: Position
    resolution_method: str  # "evidence" or "judge_ruling"
    judge_reasoning: str
    bets: list[AgentBet]
    messages: list[DebateMessage]
    position_changes: list[PositionChange]
    payouts: dict[str, float]  # agent_name -> pnl
    total_pool: float
    yes_count: int
    no_count: int


class DebateEvent(BaseModel):
    """Real-time event pushed to frontend via WebSocket."""
    type: str  # phase_change, bet, message, position_change, result
    phase: DebatePhase
    data: dict
    timestamp: datetime = Field(default_factory=datetime.now)
