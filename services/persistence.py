"""数据持久化 — JSON 文件读写"""

import json

from config import DATA_DIR, DEBATES_FILE, USED_TOPICS_FILE


def load_debates() -> dict[str, dict]:
    if not DEBATES_FILE.exists():
        return {}
    try:
        raw = DEBATES_FILE.read_text(encoding="utf-8")
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
