"""观点交易所 — 批量调度模块

从知乎热榜自动创建辩论，并定时运行待处理辩论。
"""

import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from config import BATCH_INTERVAL_SECONDS
from services.llm import get_deepseek_client
from services.persistence import (
    load_debates,
    save_debate,
    load_used_topics,
    save_used_topics,
)
from services.pricing import calculate_option_prices
from services.zhihu_api import fetch_hotlist_for_debates
from services.debate_engine import (
    generate_options_for_topic,
    run_phase1_roundtable,
    run_phase2_reveal_bet,
    run_phase3_team_defense,
    run_phase4_judgment,
)
from agents.personalities import AGENT_PERSONALITIES

# ── Module-level state ────────────────────────────────
_batch_lock = threading.Lock()
_batch_running = False
_next_batch_time: Optional[str] = None


def batch_running() -> bool:
    """Return whether a batch is currently running."""
    return _batch_running


def next_batch_time() -> Optional[str]:
    """Return the ISO-formatted timestamp of the next scheduled batch."""
    return _next_batch_time


def _create_debates_from_hotlist(
    client,
    max_debates: int = 10,
) -> list[dict]:
    """Fetch Zhihu hotlist, filter out used topics, create new debates.

    Returns list of newly created debate dicts.
    """
    topics = fetch_hotlist_for_debates(count=20)
    if not topics:
        print("[BATCH] No hotlist topics fetched")
        return []

    used_topics = load_used_topics()
    new_debates: list[dict] = []

    for topic in topics:
        if len(new_debates) >= max_debates:
            break

        title = topic["title"]
        # Skip if already used (fuzzy: strip whitespace)
        if title.strip() in used_topics:
            continue

        try:
            options = generate_options_for_topic(client, title)
            agents = list(AGENT_PERSONALITIES)

            # Calculate initial market prices
            option_keys = [o["key"] for o in options]
            initial_prices = calculate_option_prices(option_keys, [])

            debate_id = uuid.uuid4().hex[:8]
            debate = {
                "id": debate_id,
                "title": title,
                "options": options,
                "context": topic.get("detail_text", ""),
                "category": "zhihu_hotlist",
                "status": "created",
                "phase": "",
                "agents": [
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "emoji": a["emoji"],
                        "description": a["description"],
                    }
                    for a in agents
                ],
                "transcript": [],
                "bets": [],
                "market_prices": initial_prices,
                "team_defense_messages": [],
                "judgment": None,
                "payouts": None,
                "created_at": datetime.now().isoformat(),
                "source": "zhihu_hotlist",
            }

            save_debate(debate)
            new_debates.append(debate)
            used_topics.add(title.strip())
            print(f"[BATCH] Created debate from hotlist: {title[:40]}...")

        except Exception as e:
            print(f"[BATCH] Failed to create debate for '{title[:30]}': {e}")

    save_used_topics(used_topics)
    return new_debates


def run_batch_debates():
    """Auto-create new debates from Zhihu hotlist AND run pending debates.

    Flow: Create debates -> Run debates that have been pending 30+ min.
    """
    global _batch_running
    if _batch_running:
        return
    with _batch_lock:
        _batch_running = True
    try:
        client = get_deepseek_client()

        # Step 1: Create new debates from Zhihu hotlist
        print("[BATCH] Fetching Zhihu hotlist and creating debates...")
        new_debates = _create_debates_from_hotlist(client, max_debates=10)
        print(f"[BATCH] Created {len(new_debates)} new debates from hotlist")

        # Step 2: Run debates that have been pending for 30+ minutes
        debates = load_debates()
        cutoff_time = (datetime.now() - timedelta(minutes=30)).isoformat()
        pending = [
            d for d in debates.values()
            if d.get("status") == "created"
            and d.get("created_at", "") <= cutoff_time
        ]

        if not pending:
            print("[BATCH] No mature pending debates to run (waiting for joins)")
            return

        print(f"[BATCH] Starting batch: {len(pending)} mature debates")
        for debate in pending[:5]:  # Max 5 per batch to limit API cost
            try:
                print(f"[BATCH] Running: {debate['title'][:30]}...")
                # Rebuild agent list
                agents = list(AGENT_PERSONALITIES)
                builtin_ids = {a["id"] for a in AGENT_PERSONALITIES}
                for ca in debate.get("agents", []):
                    if ca["id"] not in builtin_ids:
                        agents.append({
                            "id": ca["id"],
                            "name": ca["name"],
                            "emoji": ca.get("emoji", "👤"),
                            "description": ca.get("description", ""),
                            "risk_appetite": ca.get("risk_appetite", 0.5),
                            "system_prompt": ca.get(
                                "system_prompt",
                                f"你是{ca['name']}，一个辩论参与者。请用中文发表你的观点。",
                            ),
                        })

                debate["status"] = "running"
                debate["phase"] = "圆桌讨论"
                save_debate(debate)

                transcript = run_phase1_roundtable(client, debate, agents)
                debate["transcript"] = transcript
                debate["phase"] = "亮牌下注"
                save_debate(debate)

                bets, market_prices = run_phase2_reveal_bet(
                    client, debate, agents, transcript
                )
                debate["bets"] = bets
                debate["market_prices"] = market_prices
                debate["phase"] = "站队辩护"
                save_debate(debate)

                defense_messages = run_phase3_team_defense(
                    client, debate, agents, transcript, bets
                )
                debate["team_defense_messages"] = defense_messages
                for msg in defense_messages:
                    transcript.append(msg)
                debate["transcript"] = transcript
                debate["phase"] = "刘看山裁决"
                save_debate(debate)

                judgment = run_phase4_judgment(
                    client, debate, transcript, bets, defense_messages
                )
                debate["judgment"] = judgment
                debate["payouts"] = judgment["payouts"]
                debate["status"] = "completed"
                debate["phase"] = "已结束"
                save_debate(debate)
                print(
                    f"[BATCH] Done: {debate['title'][:30]} "
                    f"-> {judgment.get('winning_label', '?')}"
                )
            except Exception as e:
                print(f"[BATCH] Error running {debate['id']}: {e}")
                debate["status"] = "created"  # Reset so it can be retried
                save_debate(debate)
    finally:
        _batch_running = False


def schedule_batch_loop():
    """Run batch debates on a timer (every 30 minutes)."""
    global _next_batch_time
    while True:
        _next_batch_time = (
            datetime.now() + timedelta(seconds=BATCH_INTERVAL_SECONDS)
        ).isoformat()
        time.sleep(BATCH_INTERVAL_SECONDS)
        try:
            run_batch_debates()
        except Exception as e:
            print(f"[BATCH] Scheduler error: {e}")
