"""数据持久化 — JSON 文件读写（带内存缓存）"""

import json
import re
import threading

from config import DATA_DIR, DEBATES_FILE, USED_TOPICS_FILE, WALLETS_FILE

# ── 文件锁：防止并发写入损坏 ──────────────────────────────
_debates_lock = threading.RLock()
_wallets_lock = threading.RLock()

# ── 内存缓存：避免每次 API 请求都读磁盘 ──────────────────
_debates_cache: dict[str, dict] = {}
_debates_mtime: float = 0.0

_wallets_cache: dict[str, dict] = {}
_wallets_mtime: float = 0.0


def _clean_control_chars(text: str) -> str:
    """移除 JSON 中的控制字符（保留换行和制表符）。"""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)


def load_debates() -> dict[str, dict]:
    global _debates_cache, _debates_mtime
    with _debates_lock:
        if not DEBATES_FILE.exists():
            return _debates_cache
        try:
            mtime = DEBATES_FILE.stat().st_mtime
            if mtime != _debates_mtime:
                raw = DEBATES_FILE.read_text(encoding="utf-8")
                raw = _clean_control_chars(raw)
                _debates_cache = json.loads(raw) if raw.strip() else {}
                _debates_mtime = mtime
            return _debates_cache
        except (json.JSONDecodeError, OSError):
            return _debates_cache


def save_debates(debates: dict[str, dict]) -> None:
    global _debates_cache, _debates_mtime
    with _debates_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DEBATES_FILE.write_text(
            json.dumps(debates, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        _debates_cache = debates
        try:
            _debates_mtime = DEBATES_FILE.stat().st_mtime
        except OSError:
            pass


def save_debate(debate: dict) -> None:
    with _debates_lock:
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
    global _wallets_cache, _wallets_mtime
    with _wallets_lock:
        if not WALLETS_FILE.exists():
            return _wallets_cache
        try:
            mtime = WALLETS_FILE.stat().st_mtime
            if mtime != _wallets_mtime:
                raw = WALLETS_FILE.read_text(encoding="utf-8")
                _wallets_cache = json.loads(raw) if raw.strip() else {}
                _wallets_mtime = mtime
            return _wallets_cache
        except (json.JSONDecodeError, OSError):
            return _wallets_cache


def save_wallets(wallets: dict[str, dict]) -> None:
    global _wallets_cache, _wallets_mtime
    with _wallets_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        WALLETS_FILE.write_text(
            json.dumps(wallets, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        _wallets_cache = wallets
        try:
            _wallets_mtime = WALLETS_FILE.stat().st_mtime
        except OSError:
            pass


def save_wallet(wallet: dict) -> None:
    with _wallets_lock:
        wallets = load_wallets()
        wallets[wallet["user_id"]] = wallet
        save_wallets(wallets)
