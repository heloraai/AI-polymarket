"""观点交易所 — FastAPI 服务器入口

知乎热榜出题，AI 辩论下注，刘看山裁定。
"""

import threading

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


@app.on_event("startup")
def startup_event():
    """启动批量调度后台线程。"""
    t = threading.Thread(target=schedule_batch_loop, daemon=True)
    t.start()
    print(
        f"[观点交易所] 服务已启动 | 批量调度间隔: {BATCH_INTERVAL_SECONDS // 60} 分钟"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
