"""数据持久化 — JSON 文件读写"""

import json
import re

from config import DATA_DIR, DEBATES_FILE, USED_TOPICS_FILE, WALLETS_FILE


def _clean_control_chars(text: str) -> str:
    """移除 JSON 中的控制字符（保留换行和制表符）。"""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)


def load_debates() -> dict[str, dict]:
    if not DEBATES_FILE.exists():
        return {}
    try:
        raw = DEBATES_FILE.read_text(encoding="utf-8")
        raw = _clean_control_chars(raw)
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_debates(debates: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DEBATES_FILE.write_text(
        json.dumps(debates, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def save_debate(debate: dict) -> None:
    debates = load_debates()
    debates[debate["id"]] = debate
    save_debates(debates)


def load_used_topics() -> set[str]:
    if not USED_TOPICS_FILE.exists():
        return set()
    try:
        raw = USED_TOPICS_FILE.read_text(encoding="utf-8")
        topics = json.loads(raw) if raw.strip() else []
        return set(topics)
    except (json.JSONDecodeError, OSError):
        return set()


def save_used_topics(topics: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USED_TOPICS_FILE.write_text(
        json.dumps(list(topics), ensure_ascii=False, indent=2), encoding="utf-8",
    )


def load_wallets() -> dict[str, dict]:
    if not WALLETS_FILE.exists():
        return {}
    try:
        raw = WALLETS_FILE.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_wallets(wallets: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WALLETS_FILE.write_text(
        json.dumps(wallets, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def save_wallet(wallet: dict) -> None:
    wallets = load_wallets()
    wallets[wallet["user_id"]] = wallet
    save_wallets(wallets)
