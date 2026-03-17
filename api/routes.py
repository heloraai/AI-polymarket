"""观点交易所 — FastAPI 路由

所有 /api 路由处理函数，从 server.py 提取并统一路径风格。
使用 /debates/{debate_id} (plural) 作为一致的路径前缀。
"""

import threading
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CreateDebateRequest,
    AutoCreateRequest,
    AddOptionRequest,
    JoinDebateRequest,
)
from agents.personalities import AGENT_PERSONALITIES, JUDGE_PERSONALITY
from services.llm import get_deepseek_client
from services.persistence import load_debates, save_debate
from services.pricing import calculate_option_prices
from services.secondme import get_secondme_profile, build_user_agent
from services.debate_engine import (
    get_agents_for_debate,
    generate_options_for_topic,
    run_phase1_roundtable,
    run_phase2_reveal_bet,
    run_phase3_team_defense,
    run_phase4_judgment,
)
from services.batch import run_batch_debates, batch_running, next_batch_time
from config import SHARE_PAYOUT, BATCH_INTERVAL_SECONDS

router = APIRouter(prefix="/api")


# ── Batch endpoints ──────────────────────────────────

@router.post("/batch/run")
def trigger_batch():
    """Manually trigger a batch run (for testing)."""
    t = threading.Thread(target=run_batch_debates, daemon=True)
    t.start()
    return {"message": "Batch run triggered"}


@router.get("/batch/status")
def batch_status():
    """Show batch scheduler status: next batch time and current pending debates."""
    debates = load_debates()
    pending = [
        {
            "id": d["id"],
            "title": d["title"],
            "created_at": d.get("created_at", ""),
            "agent_count": len(d.get("agents", [])),
            "source": d.get("source", "manual"),
        }
        for d in debates.values()
        if d.get("status") == "created"
    ]
    pending.sort(key=lambda x: x.get("created_at", ""))

    cutoff_time = (datetime.now() - timedelta(minutes=30)).isoformat()
    mature_count = sum(
        1 for d in pending if d.get("created_at", "") <= cutoff_time
    )

    return {
        "batch_running": batch_running(),
        "next_batch_time": next_batch_time(),
        "batch_interval_minutes": BATCH_INTERVAL_SECONDS // 60,
        "pending_debates": pending,
        "pending_count": len(pending),
        "mature_count": mature_count,
        "mature_description": (
            f"{mature_count} debates pending 30+ min (ready to run)"
        ),
    }


# ── Debate CRUD ──────────────────────────────────────

@router.get("/debates")
def list_debates():
    """List all debates with full data."""
    debates = load_debates()
    result = list(debates.values())
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"debates": result}


@router.post("/debates/auto")
def auto_create_debate(req: AutoCreateRequest):
    """Create a debate with LLM-generated options tailored to the topic."""
    if not req.title:
        raise HTTPException(status_code=400, detail="title is required")

    client = get_deepseek_client()
    options = generate_options_for_topic(client, req.title)

    # Reuse the normal create flow
    create_req = CreateDebateRequest(
        title=req.title,
        options=[{"key": o["key"], "label": o["label"]} for o in options],
        context=req.context,
    )
    return create_debate(create_req)


@router.post("/debates")
def create_debate(req: CreateDebateRequest):
    """Create a new debate."""
    if not req.title:
        raise HTTPException(status_code=400, detail="title is required")

    if len(req.options) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 options are required",
        )

    default_colors = [
        "#4ecdc4", "#ff6b6b", "#ffd93d",
        "#6c5ce7", "#a8e6cf", "#ff8a5c",
    ]
    options = []
    for i, opt in enumerate(req.options):
        options.append({
            "key": opt.get("key", f"option_{i}"),
            "label": opt.get("label", f"选项{i+1}"),
            "description": opt.get("description", ""),
            "color": opt.get("color", default_colors[i % len(default_colors)]),
        })

    agents = get_agents_for_debate(req.custom_agents)

    # Calculate initial market prices
    option_keys = [o["key"] for o in options]
    initial_prices = calculate_option_prices(option_keys, [], seed=req.title)

    debate_id = uuid.uuid4().hex[:8]
    debate = {
        "id": debate_id,
        "title": req.title,
        "options": options,
        "context": req.context,
        "category": req.category,
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
    }

    save_debate(debate)

    return debate


@router.post("/debates/{debate_id}/options")
def add_option_to_debate(debate_id: str, req: AddOptionRequest):
    """Add a user-suggested option to a debate BEFORE it starts (Task 4).

    Validates that the new option is meaningfully different from existing ones.
    """
    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate.get("status") != "created":
        raise HTTPException(
            status_code=400,
            detail="Cannot add options after debate has started",
        )

    if not req.label or not req.label.strip():
        raise HTTPException(status_code=400, detail="Option label is required")

    new_label = req.label.strip()

    # Validate uniqueness: check for duplicates or overly similar options
    existing_labels = [opt["label"] for opt in debate.get("options", [])]
    for existing in existing_labels:
        # Exact match
        if new_label == existing:
            raise HTTPException(
                status_code=400,
                detail=f"Option '{new_label}' already exists",
            )
        # Substring match (one contains the other)
        if new_label in existing or existing in new_label:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Option '{new_label}' is too similar to "
                    f"existing option '{existing}'"
                ),
            )

    # Max 6 options
    if len(existing_labels) >= 6:
        raise HTTPException(
            status_code=400,
            detail="Maximum 6 options per debate",
        )

    # Add the new option
    new_index = len(debate["options"])
    default_colors = [
        "#4ecdc4", "#ff6b6b", "#ffd93d",
        "#6c5ce7", "#a8e6cf", "#ff8a5c",
    ]
    new_option = {
        "key": f"option_{new_index}",
        "label": new_label,
        "description": req.description or "",
        "color": default_colors[new_index % len(default_colors)],
    }
    debate["options"].append(new_option)

    # Recalculate initial market prices with new option count
    option_keys = [o["key"] for o in debate["options"]]
    debate["market_prices"] = calculate_option_prices(option_keys, [])

    save_debate(debate)

    return {
        "message": f"Option '{new_label}' added successfully",
        "option": new_option,
        "market_prices": debate["market_prices"],
        "total_options": len(debate["options"]),
    }


@router.post("/debates/{debate_id}/join")
def join_debate(debate_id: str, req: JoinDebateRequest):
    """Add a user agent to a debate before it runs."""
    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate.get("status") not in ("created", "pending"):
        raise HTTPException(status_code=400, detail="Debate already started")

    # Check if user already joined
    agent_id = f"user_{req.user_id[:8]}"
    existing_ids = {a["id"] for a in debate.get("agents", [])}
    if agent_id in existing_ids:
        raise HTTPException(
            status_code=400, detail="User already joined this debate"
        )

    # Build user agent profile
    profile: dict = {}
    if req.soft_memory:
        profile["personality"] = (
            f"以下是你的记忆和性格片段：\n{req.soft_memory}"
        )
    elif req.access_token:
        profile = get_secondme_profile(req.access_token)

    if req.personality_override and not profile.get("personality"):
        profile["personality"] = req.personality_override

    user_agent = build_user_agent(req.user_id, req.user_name, profile)

    # Add to debate agents list
    debate["agents"].append({
        "id": user_agent["id"],
        "name": user_agent["name"],
        "emoji": user_agent["emoji"],
        "description": user_agent["description"],
        "risk_appetite": user_agent["risk_appetite"],
        "system_prompt": user_agent["system_prompt"],
        "is_user_agent": True,
    })

    save_debate(debate)

    return {
        "message": f"{user_agent['name']} 已加入辩论",
        "agent": user_agent,
        "debate_id": debate_id,
    }


@router.get("/debates/{debate_id}")
def get_debate(debate_id: str):
    """Get debate details."""
    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")
    return debate


@router.get("/debates/{debate_id}/prices")
def get_market_prices(debate_id: str):
    """Get current market prices for a debate's options."""
    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    option_keys = [o["key"] for o in debate.get("options", [])]
    prices = calculate_option_prices(option_keys, debate.get("bets", []))

    return {
        "debate_id": debate_id,
        "market_prices": prices,
        "share_payout": SHARE_PAYOUT,
        "options": [
            {
                "key": opt["key"],
                "label": opt["label"],
                "price": prices.get(opt["key"], 0),
                "potential_profit": round(
                    SHARE_PAYOUT - prices.get(opt["key"], 0), 1
                ),
            }
            for opt in debate.get("options", [])
        ],
    }


@router.post("/debates/{debate_id}/run")
def run_debate(debate_id: str):
    """Run the full 4-phase debate flow synchronously."""
    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate.get("status") == "completed":
        raise HTTPException(
            status_code=400, detail="Debate already completed"
        )

    client = get_deepseek_client()

    # Rebuild full agent list: 5 built-in + any user agents
    builtin_ids = {a["id"] for a in AGENT_PERSONALITIES}
    agents = list(AGENT_PERSONALITIES)

    for ca in debate.get("agents", []):
        if ca["id"] in builtin_ids:
            continue
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
            "is_user_agent": ca.get("is_user_agent", False),
        })

    # -- Phase 1: 圆桌讨论 --
    debate["status"] = "running"
    debate["phase"] = "圆桌讨论"
    save_debate(debate)

    transcript = run_phase1_roundtable(client, debate, agents)
    debate["transcript"] = transcript
    save_debate(debate)

    # -- Phase 2: 亮牌下注 (CPMM pricing) --
    debate["phase"] = "亮牌下注"
    save_debate(debate)

    bets, market_prices = run_phase2_reveal_bet(
        client, debate, agents, transcript
    )
    debate["bets"] = bets
    debate["market_prices"] = market_prices
    save_debate(debate)

    # -- Phase 3: 站队辩护 --
    debate["phase"] = "站队辩护"
    save_debate(debate)

    defense_messages = run_phase3_team_defense(
        client, debate, agents, transcript, bets,
    )
    debate["team_defense_messages"] = defense_messages
    for msg in defense_messages:
        transcript.append(msg)
    debate["transcript"] = transcript
    save_debate(debate)

    # -- Phase 4: 刘看山裁决 --
    debate["phase"] = "刘看山裁决"
    save_debate(debate)

    judgment = run_phase4_judgment(
        client, debate, transcript, bets, defense_messages,
    )
    debate["judgment"] = judgment
    debate["payouts"] = judgment["payouts"]
    debate["status"] = "completed"
    debate["phase"] = "已结束"
    save_debate(debate)

    # Settle user wallet holdings
    from services.wallet import settle_holdings_for_debate
    settle_holdings_for_debate(debate_id)

    # 观点出圈：获胜论点自动发布到知乎圈子
    try:
        from services.zhihu_api import publish_to_zhihu_circle
        winning_label = judgment.get("winning_label", "")
        mvp = judgment.get("mvp", "")
        reasoning = judgment.get("reasoning", "")[:300]

        # Find MVP's argument from transcript
        mvp_argument = ""
        for msg in transcript:
            agent_name = msg.get("agent_name", "")
            if agent_name == mvp and msg.get("phase", "").startswith("圆桌讨论"):
                mvp_argument = msg.get("content", "")[:200]
                break

        post_content = (
            f"【观点交易所 · AI辩论速报】\n\n"
            f"📌 辩题：{debate['title']}\n\n"
            f"🏆 胜出观点：{winning_label}\n"
            f"⭐ MVP：{mvp}\n\n"
            f"💬 核心论点：{mvp_argument or reasoning[:200]}\n\n"
            f"📊 {len(bets)} 位AI交易员参与，总池 {sum(b.get('bet_amount', 0) for b in bets)} 积分\n\n"
            f"👉 来观点交易所，用积分为你的观点下注\n"
            f"https://reconnect-hackathon.com/projects/cmmtbrbth000604jut32hadex\n\n"
            f"#观点交易所 #AI辩论 #知乎热榜"
        )

        publish_result = publish_to_zhihu_circle(post_content)
        if publish_result:
            debate["zhihu_post"] = {
                "published": True,
                "post_id": publish_result.get("pin_id", ""),
                "content": post_content,
                "published_at": datetime.now().isoformat(),
            }
            save_debate(debate)
    except Exception as e:
        print(f"[观点出圈] Failed: {e}")

    return debate


# ── Leaderboard ──────────────────────────────────────

@router.get("/leaderboard")
def get_leaderboard():
    """Calculate cumulative leaderboard from all completed debates."""
    debates = load_debates()
    stats: dict[str, dict] = {}

    for debate in debates.values():
        if debate.get("status") != "completed":
            continue
        payouts = debate.get("payouts", {})
        bets = debate.get("bets", [])

        for bet in bets:
            name = bet["agent_name"]
            if name not in stats:
                agent_def = next(
                    (a for a in AGENT_PERSONALITIES if a["name"] == name),
                    {"emoji": "🤖", "description": ""},
                )
                stats[name] = {
                    "name": name,
                    "emoji": agent_def.get("emoji", "🤖"),
                    "description": agent_def.get("description", ""),
                    "total_profit": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_bets": 0,
                    "total_wagered": 0,
                }

            stats[name]["total_bets"] += 1
            stats[name]["total_wagered"] += bet.get(
                "purchase_price", bet.get("bet_amount", 0)
            )

            payout = payouts.get(name, {})
            profit = payout.get("profit", 0)
            stats[name]["total_profit"] += profit
            if payout.get("result") == "win":
                stats[name]["wins"] += 1
            elif payout.get("result") == "lose":
                stats[name]["losses"] += 1

    leaderboard = []
    for s in stats.values():
        total = s["wins"] + s["losses"]
        s["win_rate"] = round(s["wins"] / total * 100) if total > 0 else 0
        s["total_profit"] = round(s["total_profit"], 1)
        leaderboard.append(s)

    leaderboard.sort(key=lambda x: x["total_profit"], reverse=True)

    # Add user wallets to leaderboard
    from services.wallet import calculate_net_worth
    from services.persistence import load_wallets
    wallets = load_wallets()
    for wallet in wallets.values():
        nw = calculate_net_worth(wallet)
        active_count = sum(1 for h in wallet.get("holdings", []) if h["status"] == "active")
        settled_count = sum(1 for h in wallet.get("holdings", []) if h["status"].startswith("settled"))
        wins = sum(1 for h in wallet.get("holdings", []) if h["status"] == "settled_win")
        losses = sum(1 for h in wallet.get("holdings", []) if h["status"] == "settled_lose")
        leaderboard.append({
            "name": wallet.get("user_name", "匿名"),
            "emoji": "👤",
            "description": "观点交易员",
            "total_profit": round(nw - wallet.get("initial_balance", 200.0), 1),
            "wins": wins,
            "losses": losses,
            "total_bets": active_count + settled_count,
            "total_wagered": sum(h.get("total_cost", 0) for h in wallet.get("holdings", [])),
            "win_rate": round(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "type": "user",
            "net_worth": nw,
        })
    # Users always rank above AI agents, then sort by net_worth/profit
    leaderboard.sort(
        key=lambda x: (
            1 if x.get("type") == "user" else 0,  # users first
            x.get("net_worth", x.get("total_profit", 0)),
        ),
        reverse=True,
    )

    return {"leaderboard": leaderboard}


@router.post("/recycle-completed")
def recycle_completed():
    """把已结算辩论复制为新的可买入辩论，置顶热榜。"""
    import uuid as _uuid
    from services.pricing import calculate_option_prices as _calc

    debates = load_debates()
    completed = [d for d in debates.values() if d.get("status") == "completed"]

    created_count = 0
    for old in completed:
        new_id = _uuid.uuid4().hex[:8]
        options = old.get("options", [])
        option_keys = [o["key"] for o in options]
        agents_clean = [
            {"id": a["id"], "name": a["name"], "emoji": a["emoji"], "description": a["description"]}
            for a in old.get("agents", [])
            if not a.get("is_user_agent")
        ]

        debates[new_id] = {
            "id": new_id,
            "title": old["title"],
            "options": options,
            "context": old.get("context", ""),
            "category": old.get("category", "zhihu_hotlist"),
            "status": "created",
            "phase": "",
            "agents": agents_clean,
            "transcript": [],
            "bets": [],
            "market_prices": _calc(option_keys, [], seed=old["title"]),
            "team_defense_messages": [],
            "judgment": None,
            "payouts": None,
            "created_at": datetime.now().isoformat(),
            "source": "recycled",
        }
        created_count += 1

    from services.persistence import save_debates
    save_debates(debates)

    return {"message": f"复制 {created_count} 个已结算辩论为新辩论，已置顶热榜"}


