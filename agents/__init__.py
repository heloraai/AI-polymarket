# CLI agents use anthropic SDK — lazy import to avoid dependency in Web mode
from .personalities import (
    ALL_PERSONALITIES, AGENT_PERSONALITIES,
    BULL, BEAR, FOX, OWL, DEGEN,
    JUDGE_PERSONALITY,
)

__all__ = [
    "ALL_PERSONALITIES",
    "AGENT_PERSONALITIES",
    "BULL", "BEAR", "FOX", "OWL", "DEGEN",
    "JUDGE_PERSONALITY",
]
