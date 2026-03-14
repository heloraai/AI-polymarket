"""知乎观点擂台 — FastAPI 服务器

Polymarket 风格的 AI Agent 辩论竞技场。
多选项下注 + 实时辩论 + WebSocket 推送。
"""

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import ANTHROPIC_API_KEY
from agents.personalities import ALL_PERSONALITIES
from debate.models import DebateEvent, DebateTopic, PositionOption
from debate.room import DebateRoom

app = FastAPI(title="知乎观点擂台", version="2.0.0")

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── State ─────────────────────────────────────────────
active_debates: dict[str, DebateRoom] = {}
debate_results: dict[str, dict] = {}
global_leaderboard: dict[str, dict] = {}
ws_connections: dict[str, list[WebSocket]] = {}

for p in ALL_PERSONALITIES:
    global_leaderboard[p.name] = {
        "name": p.name,
        "emoji": p.emoji,
        "description": p.description,
        "total_score": 0,
        "wins": 0,
        "losses": 0,
        "debates": 0,
        "persuasions_caused": 0,
        "times_persuaded": 0,
    }

# ── Multi-Option Topics (Polymarket-style) ────────────

OPTION_COLORS = ["#4ecdc4", "#ff6b6b", "#ffd93d", "#6c5ce7", "#a8e6cf", "#ff8a5c"]

STUB_TOPICS = [
    DebateTopic(
        title="AI 编程 Agent 将如何改变程序员的工作？",
        category="科技",
        context=(
            "Devin、Claude Code、Cursor 等 AI 编程工具引发热议。"
            "知乎上关于'程序员是否会失业'的讨论持续升温。"
            "各方观点激烈碰撞。"
        ),
        hot_score=98.5,
        options=[
            PositionOption(key="replace", label="大规模取代", description="3年内大部分初中级程序员工作将被AI替代", color="#ff6b6b"),
            PositionOption(key="augment", label="增强而非取代", description="AI成为超级工具，程序员效率10x但不会失业", color="#4ecdc4"),
            PositionOption(key="split", label="两极分化", description="顶尖程序员更强，普通程序员被淘汰", color="#ffd93d"),
            PositionOption(key="bubble", label="AI泡沫论", description="当前AI能力被高估，程序员工作本质不变", color="#6c5ce7"),
        ],
    ),
    DebateTopic(
        title="中国新能源车的全球霸主地位能维持多久？",
        category="汽车",
        context=(
            "2025年中国新能源汽车渗透率突破50%，比亚迪全球销量超越丰田。"
            "但欧美关税壁垒加剧，丰田固态电池即将量产。"
            "知乎汽车区讨论热烈。"
        ),
        hot_score=92.3,
        options=[
            PositionOption(key="decade", label="至少10年", description="技术+供应链+规模优势形成护城河", color="#4ecdc4"),
            PositionOption(key="peak", label="已达顶峰", description="关税+固态电池+品牌力不足将逆转局势", color="#ff6b6b"),
            PositionOption(key="domestic", label="墙内开花", description="国内称霸但出海受阻，形成割据局面", color="#ffd93d"),
            PositionOption(key="leapfrog", label="被跨越", description="下一代技术(氢能/固态)将重新洗牌", color="#6c5ce7"),
        ],
    ),
    DebateTopic(
        title="年轻人'不婚不育'的根本原因是什么？",
        category="社会",
        context=(
            "中国人口连续多年负增长。知乎上万条回答探讨年轻人不婚不育现象。"
            "经济压力、价值观变迁、社会制度、个人自由等角度激烈碰撞。"
        ),
        hot_score=96.1,
        options=[
            PositionOption(key="economic", label="经济压力", description="房价+教育+医疗成本让年轻人生不起", color="#ff6b6b"),
            PositionOption(key="values", label="价值观进化", description="个体意识觉醒，婚育不再是人生必选项", color="#4ecdc4"),
            PositionOption(key="system", label="制度缺陷", description="社会保障不足+性别不平等+职场歧视", color="#ffd93d"),
            PositionOption(key="global", label="全球趋势", description="发达社会的普遍现象，与中国特殊性无关", color="#6c5ce7"),
        ],
    ),
    DebateTopic(
        title="短视频是在摧毁还是民主化知识传播？",
        category="文化",
        context=(
            "抖音日活超过7亿，人均使用时长超过2小时。"
            "知乎上关于短视频对认知能力影响的讨论引发广泛关注。"
            "有人说碎片化毁灭深度思考，有人说知识从未如此平等可得。"
        ),
        hot_score=91.4,
        options=[
            PositionOption(key="destroy", label="认知毒药", description="碎片化摧毁注意力和深度思考能力", color="#ff6b6b"),
            PositionOption(key="democratize", label="知识民主化", description="打破信息垄断，让知识触达更多人", color="#4ecdc4"),
            PositionOption(key="both", label="双刃剑", description="取决于使用方式，工具本身无善恶", color="#ffd93d"),
            PositionOption(key="evolve", label="认知进化", description="人类大脑正在适应新的信息处理模式", color="#6c5ce7"),
        ],
    ),
    DebateTopic(
        title="大模型的'涌现能力'是真的突破还是统计幻觉？",
        category="AI",
        context=(
            "GPT-4、Claude 等大模型展现出似乎超越训练数据的推理能力。"
            "学界对'涌现'(emergence)是否真实存在争论不断。"
            "知乎 AI 区关于这个话题的讨论涉及哲学、认知科学和工程实践。"
        ),
        hot_score=89.2,
        options=[
            PositionOption(key="real", label="真正涌现", description="规模突破临界点产生了质变，是真正的智能萌芽", color="#4ecdc4"),
            PositionOption(key="illusion", label="统计幻觉", description="只是超大规模模式匹配，本质上是随机鹦鹉", color="#ff6b6b"),
            PositionOption(key="partial", label="能力真实但不是涌现", description="能力是连续提升的，'涌现'只是度量方式的产物", color="#ffd93d"),
            PositionOption(key="unknowable", label="不可知论", description="我们目前的理论框架不足以回答这个问题", color="#6c5ce7"),
        ],
    ),
]


# ── Routes ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = static_dir / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/topics")
async def get_topics():
    return {
        "topics": [t.model_dump() for t in STUB_TOPICS],
        "source": "stub",
    }


@app.post("/api/debate/start")
async def start_debate(topic_id: str = "", topic_index: int = 0):
    if topic_id:
        topic = next((t for t in STUB_TOPICS if t.id == topic_id), None)
    elif 0 <= topic_index < len(STUB_TOPICS):
        topic = STUB_TOPICS[topic_index]
    else:
        topic = STUB_TOPICS[0]

    if topic is None:
        return {"error": "Topic not found"}

    debate_id = uuid.uuid4().hex[:8]
    room = DebateRoom(
        topic=topic,
        personalities=ALL_PERSONALITIES,
        anthropic_api_key=ANTHROPIC_API_KEY,
        base_stake=100.0,
    )
    active_debates[debate_id] = room
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
    }


@app.get("/api/leaderboard")
async def get_leaderboard():
    sorted_board = sorted(
        global_leaderboard.values(),
        key=lambda x: (x["wins"], x["total_score"]),
        reverse=True,
    )
    return {"leaderboard": sorted_board}


@app.websocket("/ws/debate/{debate_id}")
async def debate_websocket(websocket: WebSocket, debate_id: str):
    await websocket.accept()
    if debate_id not in ws_connections:
        ws_connections[debate_id] = []
    ws_connections[debate_id].append(websocket)

    try:
        room = active_debates.get(debate_id)
        if room:
            for event in room.events:
                await websocket.send_json({
                    "type": event.type,
                    "phase": event.phase.value,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                })
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
    async def broadcast_event(event: DebateEvent):
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
        debate_results[debate_id] = result.model_dump()

        # Update leaderboard
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
        if debate_id in active_debates:
            del active_debates[debate_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
