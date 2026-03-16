"""观点交易所 — Pydantic 请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JoinDebateRequest(BaseModel):
    """Request to add a user agent to a debate."""
    user_id: str
    user_name: str = ""
    access_token: str = ""  # Second Me OAuth token
    personality_override: str = ""  # Manual override if no Second Me
    soft_memory: str = ""  # Second Me soft memory fragments (joined by newline)


class CreateDebateRequest(BaseModel):
    title: str
    options: list[dict] = Field(
        default_factory=list,
        description="List of {key, label, description?, color?} option dicts",
    )
    context: str = ""
    category: str = "general"
    custom_agents: list[dict] = Field(
        default_factory=list,
        description="Optional user-defined agents [{name, emoji, description, system_prompt}]",
    )


class AddOptionRequest(BaseModel):
    """Request to add a user-suggested option to a debate before it starts."""
    label: str
    description: str = ""


class AutoCreateRequest(BaseModel):
    """Create debate with auto-generated options."""
    title: str
    context: str = ""


class DebateMessage(BaseModel):
    agent_id: str
    agent_name: str
    agent_emoji: str
    content: str
    phase: str
    round_num: int
    target_agent: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentBet(BaseModel):
    agent_id: str
    agent_name: str
    agent_emoji: str
    chosen_option: str
    chosen_label: str
    bet_amount: float
    purchase_price: float  # price paid per share at time of bet
    confidence: float
    reasoning: str


class DebateState(BaseModel):
    id: str
    title: str
    options: list[dict]
    context: str
    category: str
    status: str = "created"  # created, running, completed
    phase: str = ""
    agents: list[dict] = Field(default_factory=list)
    transcript: list[dict] = Field(default_factory=list)
    bets: list[dict] = Field(default_factory=list)
    market_prices: dict = Field(default_factory=dict)  # current option prices
    team_defense_messages: list[dict] = Field(default_factory=list)
    judgment: Optional[dict] = None
    payouts: Optional[dict] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
