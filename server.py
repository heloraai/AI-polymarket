"""观点交易所 — FastAPI 服务器入口

知乎热榜出题，AI 辩论下注，刘看山裁定。
"""

import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.wallet_routes import wallet_router
from services.batch import schedule_batch_loop
from config import CORS_ORIGINS, BATCH_INTERVAL_SECONDS

app = FastAPI(
    title="观点交易所",
    description="知乎热榜出题，AI Agent 辩论下注，刘看山裁定真相",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(wallet_router)


@app.get("/")
def health_check():
    """Render 健康检查 + 防止免费版睡眠的 ping 端点。"""
    return {"status": "ok", "service": "观点交易所"}


@app.on_event("startup")
def startup_event():
    """启动批量调度后台线程。"""
    # 若持久化磁盘为空（首次挂载），从镜像内置的 seed 数据初始化
    data_dir = Path("/app/data")
    seed_dir = Path("/app/data_seed")
    if seed_dir.exists():
        for seed_file in seed_dir.iterdir():
            target = data_dir / seed_file.name
            if not target.exists():
                shutil.copy2(seed_file, target)
                print(f"[观点交易所] 从 seed 初始化: {seed_file.name}")

    # 从已完成辩论回收出热榜内容（不需要 LLM，秒级完成）
    from services.persistence import load_debates, save_debates
    from services.pricing import calculate_option_prices
    debates = load_debates()
    created_count = sum(1 for d in debates.values() if d.get("status") == "created")
    if created_count < 50:
        completed = [d for d in debates.values() if d.get("status") == "completed"]

        # ── 过滤政治敏感话题 ──
        sensitive_keywords = [
            "特朗普", "拜登", "习近平", "普京", "泽连斯基",
            "台湾", "台海", "统一", "独立",
            "伊朗", "北约", "俄乌", "俄罗斯", "乌克兰",
            "美军", "战争", "袭击", "革命", "政权",
            "共产", "民主党", "共和党",
            "新疆", "西藏", "香港",
            "制裁", "核武", "导弹",
        ]
        completed = [
            d for d in completed
            if not any(kw in d.get("title", "") for kw in sensitive_keywords)
        ]

        # ── 按原辩论参与度排序（下注总额高 = 话题更有价值） ──
        completed.sort(
            key=lambda d: sum(b.get("bet_amount", 0) for b in d.get("bets", [])),
            reverse=True,
        )

        # ── 话题打散：按关键词聚类，同类不连续出现 ──
        topic_tags = {
            "国际": ["伊朗", "特朗普", "美国", "北约", "俄", "乌克兰", "日本", "韩"],
            "体育": ["NBA", "赛季", "世界杯", "奥运", "湖人", "马刺"],
            "科技": ["AI", "人工智能", "大模型", "芯片", "小米", "苹果", "特斯拉"],
            "娱乐": ["漫画", "电影", "剧", "游戏", "CS", "奥斯卡"],
            "财经": ["股", "基金", "房价", "油价", "降息", "LPR", "美元"],
        }

        def _get_tag(title: str) -> str:
            for tag, keywords in topic_tags.items():
                if any(kw in title for kw in keywords):
                    return tag
            return "其他"

        # 按 tag 分桶
        buckets: dict[str, list] = {}
        for d in completed:
            tag = _get_tag(d.get("title", ""))
            buckets.setdefault(tag, []).append(d)

        # 交错合并：每轮从各桶取一条，保证同类话题不连续
        interleaved: list[dict] = []
        while any(buckets.values()):
            for tag in list(buckets.keys()):
                if buckets[tag]:
                    interleaved.append(buckets[tag].pop(0))
                else:
                    del buckets[tag]

        for old in interleaved[:60]:
            new_id = uuid.uuid4().hex[:8]
            options = old.get("options", [])
            option_keys = [o["key"] for o in options]
            debates[new_id] = {
                "id": new_id,
                "title": old["title"],
                "options": options,
                "context": old.get("context", ""),
                "category": old.get("category", "zhihu_hotlist"),
                "status": "created",
                "phase": "",
                "agents": [
                    {"id": a["id"], "name": a["name"], "emoji": a["emoji"], "description": a["description"]}
                    for a in old.get("agents", []) if not a.get("is_user_agent")
                ],
                "transcript": [],
                "bets": [],
                "market_prices": calculate_option_prices(option_keys, [], seed=old["title"]),
                "team_defense_messages": [],
                "judgment": None,
                "payouts": None,
                "created_at": datetime.now().isoformat(),
                "source": "recycled",
            }
        save_debates(debates)
        recycled = sum(1 for d in debates.values() if d.get("status") == "created") - created_count
        print(f"[观点交易所] 回收 {recycled} 条已完成辩论到热榜（按参与度排序+话题打散）")

    t = threading.Thread(target=schedule_batch_loop, daemon=True)
    t.start()
    print(
        f"[观点交易所] 服务已启动 | 批量调度间隔: {BATCH_INTERVAL_SECONDS // 60} 分钟"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
