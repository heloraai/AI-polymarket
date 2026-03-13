"""项目配置"""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ZHIHU_COOKIE = os.getenv("ZHIHU_COOKIE", "")

# 预测市场设置
INITIAL_BALANCE = 1000.0      # 每个 Agent 的初始虚拟积分
MAX_BET_RATIO = 0.1           # 单笔最大下注比例
HOTLIST_SCAN_INTERVAL = 3600  # 热榜扫描间隔（秒）
