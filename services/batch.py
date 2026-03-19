"""观点交易所 — 批量调度

保证用户随时有可买入的辩论。
"""

import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from agents.personalities import AGENT_PERSONALITIES
from services.llm import get_deepseek_client
from services.persistence import load_debates, save_debate, load_used_topics, save_used_topics
from services.pricing import calculate_option_prices
from services.zhihu_api import fetch_hotlist_for_debates
from services.debate_engine import (
    generate_options_for_topic,
    run_phase1_roundtable, run_phase2_reveal_bet,
    run_phase3_team_defense, run_phase4_judgment,
)
from config import BATCH_INTERVAL_SECONDS

_batch_lock = threading.Lock()
_batch_running = False
_next_batch_time: Optional[str] = None

MIN_AVAILABLE_DEBATES = 10
INITIAL_BATCH_SIZE = 50   # 启动时拉50条
HOURLY_BATCH_SIZE = 30    # 每小时补30条


def batch_running() -> bool:
    return _batch_running


def next_batch_time() -> Optional[str]:
    return _next_batch_time


def _ensure_available_debates(client, max_create: int = 20) -> int:
    """确保始终有足够的可买入辩论。不够就拉热榜补充。"""
    debates = load_debates()
    available = [
        d for d in debates.values()
        if d.get("status") == "created"
    ]

    if len(available) >= MIN_AVAILABLE_DEBATES:
        print(f"[BATCH] {len(available)} debates available, enough")
        return 0

    need = max(max_create, MIN_AVAILABLE_DEBATES - len(available))
    print(f"[BATCH] Only {len(available)} available, creating up to {need}")

    used_topics = load_used_topics()

    topics = fetch_hotlist_for_debates(count=100)
    if not topics:
        print("[BATCH] No hotlist topics fetched")
        return 0

    created = 0
    for topic in topics:
        if created >= need:
            break

        title = topic["title"]
        if title.strip() in used_topics:
            continue

        try:
            options = generate_options_for_topic(client, title)
            agents = list(AGENT_PERSONALITIES)
            option_keys = [o["key"] for o in options]
            initial_prices = calculate_option_prices(option_keys, [], seed=title)

            debate = {
                "id": uuid.uuid4().hex[:8],
                "title": title,
                "options": options,
                "context": topic.get("detail_text", ""),
                "category": "zhihu_hotlist",
                "status": "created",
                "phase": "",
                "agents": [
                    {"id": a["id"], "name": a["name"], "emoji": a["emoji"], "description": a["description"]}
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
                "source_token": topic.get("question_token", ""),
            }
            save_debate(debate)
            created += 1
            used_topics.add(title.strip())
            print(f"[BATCH] Created: {title[:40]}...")
        except Exception as e:
            print(f"[BATCH] Failed for '{title[:30]}': {e}")

    save_used_topics(used_topics)
    print(f"[BATCH] Created {created} new debates")
    return created


def run_batch_debates():
    """自动补充辩论 + 运行已到期的辩论。"""
    global _batch_running
    if _batch_running:
        return
    with _batch_lock:
        _batch_running = True
    try:
        client = get_deepseek_client()

        # 修复卡住的辩论（running超过10分钟没完成的，重置为created）
        debates = load_debates()
        cutoff = (datetime.now() - timedelta(minutes=10)).isoformat()
        for debate in debates.values():
            if debate.get("status") == "running" and not debate.get("judgment"):
                created_at = debate.get("created_at", "")
                if created_at and created_at < cutoff:
                    print(f"[BATCH] Fixing stuck debate: {debate['id']}")
                    debate["status"] = "created"
                    debate["phase"] = ""
                    debate["transcript"] = []
                    debate["bets"] = []
                    save_debate(debate)

        # 只创建辩论，不自动跑。辩论只在用户买入时触发。
        _ensure_available_debates(client, max_create=HOURLY_BATCH_SIZE)

    finally:
        _batch_running = False


def schedule_batch_loop():
    """启动时立即拉热榜，然后定时循环。"""
    global _next_batch_time

    # 启动时立即拉50条
    try:
        print(f"[BATCH] Startup: creating {INITIAL_BATCH_SIZE} debates...")
        client = get_deepseek_client()
        _ensure_available_debates(client, max_create=INITIAL_BATCH_SIZE)
    except Exception as e:
        print(f"[BATCH] Startup error: {e}")

    while True:
        _next_batch_time = (
            datetime.now() + timedelta(seconds=BATCH_INTERVAL_SECONDS)
        ).isoformat()
        time.sleep(BATCH_INTERVAL_SECONDS)
        try:
            run_batch_debates()
        except Exception as e:
            print(f"[BATCH] Scheduler error: {e}")
