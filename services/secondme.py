"""Second Me 集成 — 用户 Agent 画像"""

import hashlib
import json
import urllib.request

from config import SECONDME_API_BASE

DEFAULT_USER_PERSONALITIES = [
    "你是一个理性的普通人，喜欢从实际生活出发思考问题。",
    "你是一个热情的理想主义者，关心社会公平和进步。",
    "你是一个实用主义者，看重成本收益和可操作性。",
    "你是一个怀疑论者，对权威观点保持警惕。",
]


def get_secondme_profile(access_token: str) -> dict:
    try:
        req = urllib.request.Request(
            f"{SECONDME_API_BASE}/user/me/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get("data", {})
    except Exception:
        return {}


def build_user_agent(user_id: str, user_name: str, profile: dict) -> dict:
    personality = (profile.get("personality") or "").strip()
    bio = (profile.get("bio") or "").strip()

    if not personality:
        idx = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % len(DEFAULT_USER_PERSONALITIES)
        personality = DEFAULT_USER_PERSONALITIES[idx]

    display_name = user_name or profile.get("name", "匿名选手")

    system_prompt = (
        f"你是「{display_name}」，一个来自知乎的真实用户Agent。\n"
        f"{'你的个人简介：' + bio + chr(10) if bio else ''}"
        f"你的性格特点：{personality}\n"
        f"你基于自己的真实性格和经历来思考问题，而非扮演角色。\n"
        f"请用中文回答，保持你的个人风格。"
    )

    return {
        "id": f"user_{user_id[:8]}",
        "name": display_name,
        "emoji": "👤",
        "description": personality[:50],
        "risk_appetite": 0.5,
        "system_prompt": system_prompt,
        "is_user_agent": True,
    }
