"""知乎观点擂台 — FastAPI 服务器

API:
  GET  /                    → 主页面
  GET  /api/topics          → 获取可用话题列表
  POST /api/debate/start    → 开始一场新辩论
  GET  /api/debate/{id}     → 获取辩论状态
  GET  /api/leaderboard     → 全局排行榜
  WS   /ws/debate/{id}      → 实时辩论事件流
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import ANTHROPIC_API_KEY
from agents.personalities import ALL_PERSONALITIES
from debate.models import DebateEvent, DebatePhase, DebateTopic
from debate.room import DebateRoom

app = FastAPI(title="知乎观点擂台", version="1.0.0")

# Serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── State ─────────────────────────────────────────────
# In-memory state (for hackathon demo; production would use DB)
active_debates: dict[str, DebateRoom] = {}
debate_results: dict[str, dict] = {}
global_leaderboard: dict[str, dict] = {}

# Initialize leaderboard
for p in ALL_PERSONALITIES:
    global_leaderboard[p.name] = {
        "name": p.name,
        "emoji": p.emoji,
        "description": p.description,
        "total_score": 0,
        "wins": 0,
        "losses": 0,
        "debates": 0,
        "persuasions_caused": 0,  # Times this agent changed others' minds
        "times_persuaded": 0,     # Times this agent was persuaded
    }

# WebSocket connections per debate
ws_connections: dict[str, list[WebSocket]] = {}

# ── Zhihu Topics (stubs until real API tomorrow) ──────

STUB_TOPICS = [
    DebateTopic(
        title="AI 是否会在 2027 年前取代大部分程序员的工作？",
        category="科技",
        context=(
            "近期 Claude、GPT 等大模型展示了强大的代码能力，"
            "Devin 等 AI 编程 Agent 引发热议。知乎上关于'程序员是否会失业'的讨论持续升温。"
            "支持方认为 AI 编程能力指数增长，重复性代码工作将被替代；"
            "反对方认为软件工程远不止写代码，架构设计和需求理解仍需人类。"
        ),
        hot_score=98.5,
    ),
    DebateTopic(
        title="新能源车是否已经全面超越燃油车？",
        category="汽车",
        context=(
            "2025年中国新能源汽车渗透率突破50%，比亚迪全球销量超越丰田。"
            "知乎上关于'电车vs油车'的讨论激烈。"
            "支持方强调性价比、智驾能力、环保优势；"
            "反对方指出续航焦虑、充电基础设施、保值率等痛点依然存在。"
        ),
        hot_score=92.3,
    ),
    DebateTopic(
        title="年轻人'不婚不育'是理性选择还是社会问题？",
        category="社会",
        context=(
            "中国人口连续多年负增长，2025年出生人口创历史新低。"
            "知乎上关于年轻人选择不婚不育的讨论引发上万条回答。"
            "支持方认为这是个人自由和经济理性的体现；"
            "反对方担忧人口结构、养老体系和社会活力受到威胁。"
        ),
        hot_score=96.1,
    ),
    DebateTopic(
        title="中国高校是否应该大规模取消文科专业？",
        category="教育",
        context=(
            "多所高校宣布缩减或取消部分文科专业，引发'文科无用论'讨论。"
            "知乎上关于文理科价值的辩论持续数月。"
            "支持方认为应聚焦理工科培养实用人才；"
            "反对方认为人文素养是社会的根基，不能用'有用'衡量。"
        ),
        hot_score=88.7,
    ),
    DebateTopic(
        title="短视频是否正在摧毁年轻人的深度思考能力？",
        category="文化",
        context=(
            "抖音日活超过7亿，人均使用时长超过2小时。"
            "知乎上关于短视频对认知能力影响的讨论引发广泛关注。"
            "支持方引用脑科学研究指出注意力碎片化的危害；"
            "反对方认为这是信息民主化，不应精英主义地否定。"
        ),
        hot_score=91.4,
    ),
]


# ── Routes ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main page."""
    html_path = static_dir / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/topics")
async def get_topics():
    """Get available debate topics."""
    # TODO: Replace with real Zhihu API when available
    return {
        "topics": [t.model_dump() for t in STUB_TOPICS],
        "source": "stub",  # Will change to "zhihu" when API is ready
    }


@app.post("/api/debate/start")
async def start_debate(topic_id: str = "", topic_index: int = 0):
    """Start a new debate on a topic."""
    # Find topic
    if topic_id:
        topic = next((t for t in STUB_TOPICS if t.id == topic_id), None)
    elif 0 <= topic_index < len(STUB_TOPICS):
        topic = STUB_TOPICS[topic_index]
    else:
        topic = STUB_TOPICS[0]

    if topic is None:
        return {"error": "Topic not found"}

    # Create debate room
    debate_id = uuid.uuid4().hex[:8]
    room = DebateRoom(
        topic=topic,
        personalities=ALL_PERSONALITIES,
        anthropic_api_key=ANTHROPIC_API_KEY,
        initial_stake=100.0,
    )
    active_debates[debate_id] = room

    # Run debate in background
    asyncio.create_task(_run_debate(debate_id, room))

    return {
        "debate_id": debate_id,
        "topic": topic.model_dump(),
        "agents": [
            {"name": p.name, "emoji": p.emoji, "description": p.description}
            for p in ALL_PERSONALITIES
        ],
    }


@app.get("/api/debate/{debate_id}")
async def get_debate(debate_id: str):
    """Get current debate state."""
    if debate_id in debate_results:
        return {"status": "completed", "result": debate_results[debate_id]}

    room = active_debates.get(debate_id)
    if room is None:
        return {"status": "not_found"}

    return {
        "status": "in_progress",
        "phase": room.phase.value,
        "topic": room.topic.model_dump(),
        "bets": [b.model_dump() for b in room.bets],
        "messages": [m.model_dump() for m in room.messages],
        "events_count": len(room.events),
    }


@app.get("/api/leaderboard")
async def get_leaderboard():
    """Get global agent leaderboard."""
    sorted_board = sorted(
        global_leaderboard.values(),
        key=lambda x: (x["wins"], x["total_score"]),
        reverse=True,
    )
    return {"leaderboard": sorted_board}


# ── WebSocket ─────────────────────────────────────────

@app.websocket("/ws/debate/{debate_id}")
async def debate_websocket(websocket: WebSocket, debate_id: str):
    """Real-time debate event stream."""
    await websocket.accept()

    if debate_id not in ws_connections:
        ws_connections[debate_id] = []
    ws_connections[debate_id].append(websocket)

    try:
        # Send any existing events (for reconnection)
        room = active_debates.get(debate_id)
        if room:
            for event in room.events:
                await websocket.send_json({
                    "type": event.type,
                    "phase": event.phase.value,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                })

        # Keep connection alive
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    finally:
        if debate_id in ws_connections:
            ws_connections[debate_id] = [
                ws for ws in ws_connections[debate_id] if ws != websocket
            ]


# ── Background Tasks ─────────────────────────────────

async def _run_debate(debate_id: str, room: DebateRoom):
    """Run a debate and broadcast events."""

    async def broadcast_event(event: DebateEvent):
        """Push event to all WebSocket connections."""
        data = {
            "type": event.type,
            "phase": event.phase.value,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
        }
        connections = ws_connections.get(debate_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.remove(ws)

    room.on_event(broadcast_event)

    try:
        result = await room.run()

        # Store result
        debate_results[debate_id] = result.model_dump()

        # Update global leaderboard
        for agent_name, pnl in result.payouts.items():
            if agent_name in global_leaderboard:
                lb = global_leaderboard[agent_name]
                lb["debates"] += 1
                lb["total_score"] += pnl
                if pnl > 0:
                    lb["wins"] += 1
                elif pnl < 0:
                    lb["losses"] += 1

        for change in result.position_changes:
            if change.influenced_by and change.influenced_by in global_leaderboard:
                global_leaderboard[change.influenced_by]["persuasions_caused"] += 1
            if change.agent_name in global_leaderboard:
                global_leaderboard[change.agent_name]["times_persuaded"] += 1

    except Exception as e:
        print(f"[Debate {debate_id}] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if debate_id in active_debates:
            del active_debates[debate_id]


# ── Run ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
