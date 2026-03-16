"""观点交易所 — 项目配置"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM 配置 ─────────────────────────────────────────
# CLI 模式使用 Anthropic (Claude)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Web 模式使用 DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ── 知乎 OpenAPI 配置（黑客松官方接口） ────────────────
ZHIHU_OPENAPI_BASE = "https://openapi.zhihu.com"
ZHIHU_APP_KEY = os.getenv("ZHIHU_APP_KEY", "")        # 用户 token
ZHIHU_APP_SECRET = os.getenv("ZHIHU_APP_SECRET", "")   # 应用密钥

# 旧版 Cookie 方式（兼容回退）
ZHIHU_COOKIE = os.getenv("ZHIHU_COOKIE", "")

# ── 数据存储 ──────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DEBATES_FILE = DATA_DIR / "debates.json"
USED_TOPICS_FILE = DATA_DIR / "used_topics.json"

# ── 预测市场设置 ──────────────────────────────────────
INITIAL_BALANCE = 1000.0
MAX_BET_RATIO = 0.1
SHARE_PAYOUT = 100

# ── Web 服务配置 ──────────────────────────────────────
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# ── Second Me 集成 ────────────────────────────────────
SECONDME_API_BASE = "https://api.mindverse.com/gate/lab"

# ── 批量调度 ──────────────────────────────────────────
BATCH_INTERVAL_SECONDS = 30 * 60
HOTLIST_SCAN_INTERVAL = 3600
