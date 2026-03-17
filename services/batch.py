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
HOURLY_BATCH_SIZE = 20    # 每小时补20条


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

        # Step 1: 补充可买入辩论（每次补20条）
        _ensure_available_debates(client, max_create=HOURLY_BATCH_SIZE)

        # Step 2: 自动运行到期的辩论（创建1分钟后）
        debates = load_debates()
        cutoff_time = (datetime.now() - timedelta(minutes=1)).isoformat()
        pending = [
            d for d in debates.values()
            if d.get("status") == "created"
            and d.get("created_at", "") <= cutoff_time
        ]

        if not pending:
            print("[BATCH] No mature pending debates")
            return

        # 每批最多跑5个，不要全跑完（留一些给用户买入）
        to_run = pending[:5]
        print(f"[BATCH] Running {len(to_run)} mature debates")

        for i, debate in enumerate(to_run):
            if i > 0:
                time.sleep(30)
            try:
                print(f"[BATCH] Running ({i+1}/{len(to_run)}): {debate['title'][:30]}...")
                agents = list(AGENT_PERSONALITIES)
                builtin_ids = {a["id"] for a in AGENT_PERSONALITIES}
                for ca in debate.get("agents", []):
                    if ca["id"] not in builtin_ids:
                        agents.append({
                            "id": ca["id"], "name": ca["name"],
                            "emoji": ca.get("emoji", "👤"),
                            "description": ca.get("description", ""),
                            "risk_appetite": ca.get("risk_appetite", 0.5),
                            "system_prompt": ca.get("system_prompt",
                                f"你是{ca['name']}，一个辩论参与者。请用中文发表你的观点。"),
                        })

                debate["status"] = "running"
                debate["phase"] = "圆桌讨论"
                save_debate(debate)

                transcript = run_phase1_roundtable(client, debate, agents)
                debate["transcript"] = transcript
                debate["phase"] = "亮牌下注"
                save_debate(debate)

                bets, market_prices = run_phase2_reveal_bet(client, debate, agents, transcript)
                debate["bets"] = bets
                debate["market_prices"] = market_prices
                debate["phase"] = "站队辩护"
                save_debate(debate)

                defense_messages = run_phase3_team_defense(client, debate, agents, transcript, bets)
                debate["team_defense_messages"] = defense_messages
                for msg in defense_messages:
                    transcript.append(msg)
                debate["transcript"] = transcript
                debate["phase"] = "刘看山裁决"
                save_debate(debate)

                judgment = run_phase4_judgment(client, debate, transcript, bets, defense_messages)
                debate["judgment"] = judgment
                debate["payouts"] = judgment["payouts"]
                debate["status"] = "completed"
                debate["phase"] = "已结束"
                save_debate(debate)

                # Settle wallets
                from services.wallet import settle_holdings_for_debate
                settle_holdings_for_debate(debate["id"])

                # Post to Zhihu
                try:
                    from services.zhihu_api import publish_to_zhihu_circle
                    winning_label = judgment.get("winning_label", "")
                    mvp = judgment.get("mvp", "")
                    mvp_argument = ""
                    for msg in transcript:
                        if msg.get("agent_name") == mvp and msg.get("phase", "").startswith("圆桌讨论"):
                            mvp_argument = msg.get("content", "")[:200]
                            break
                    post_content = (
                        f"【观点交易所 · AI辩论速报】\n\n"
                        f"📌 辩题：{debate['title']}\n\n"
                        f"🏆 胜出观点：{winning_label}\n"
                        f"⭐ MVP：{mvp}\n\n"
                        f"💬 核心论点：{mvp_argument or judgment.get('reasoning', '')[:200]}\n\n"
                        f"👉 来观点交易所，用积分为你的观点下注\n"
                        f"https://reconnect-hackathon.com/projects/cmmtbrbth000604jut32hadex\n\n"
                        f"#观点交易所 #AI辩论 #知乎热榜"
                    )
                    result = publish_to_zhihu_circle(post_content)
                    if result:
                        debate["zhihu_post"] = {
                            "published": True,
                            "post_id": result.get("content_token", ""),
                            "content": post_content,
                            "published_at": datetime.now().isoformat(),
                        }
                        save_debate(debate)
                except Exception as e:
                    print(f"[BATCH] Zhihu post failed: {e}")

                print(f"[BATCH] Done: {debate['title'][:30]} -> {judgment.get('winning_label', '?')}")
            except Exception as e:
                print(f"[BATCH] Error {debate['id']}: {e}")
                debate["status"] = "created"
                save_debate(debate)

        # Step 3: 跑完后再检查一次
        _ensure_available_debates(client, max_create=10)

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
