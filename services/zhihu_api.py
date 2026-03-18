"""知乎 OpenAPI 客户端 — 黑客松官方接口

接入两个核心接口：
1. 热榜列表 (GET /openapi/billboard/list) — 获取知乎热榜话题+回答
2. 全网可信搜 (GET /openapi/search/global) — 搜索知乎问答/文章

鉴权方式：HMAC-SHA256 签名
"""

import base64
import hashlib
import hmac
import time
import uuid

import threading

import httpx

_search_lock = threading.Lock()
_last_search_time = 0.0

from config import ZHIHU_OPENAPI_BASE, ZHIHU_APP_KEY, ZHIHU_APP_SECRET


def _generate_sign_headers() -> dict[str, str]:
    """生成知乎 OpenAPI 鉴权请求头。"""
    if not ZHIHU_APP_KEY or not ZHIHU_APP_SECRET:
        raise ValueError("ZHIHU_APP_KEY and ZHIHU_APP_SECRET must be set")

    timestamp = str(int(time.time()))
    log_id = f"log_{uuid.uuid4().hex[:16]}"
    extra_info = ""

    sign_string = f"app_key:{ZHIHU_APP_KEY}|ts:{timestamp}|logid:{log_id}|extra_info:{extra_info}"
    signature = base64.b64encode(
        hmac.new(
            ZHIHU_APP_SECRET.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    return {
        "X-App-Key": ZHIHU_APP_KEY,
        "X-Timestamp": timestamp,
        "X-Log-Id": log_id,
        "X-Extra-Info": extra_info,
        "X-Sign": signature,
    }


def fetch_billboard(top_cnt: int = 50, publish_in_hours: int = 48) -> list[dict]:
    """获取知乎热榜列表 (API 2)。"""
    headers = _generate_sign_headers()
    resp = httpx.get(
        f"{ZHIHU_OPENAPI_BASE}/openapi/billboard/list",
        params={"top_cnt": top_cnt, "publish_in_hours": publish_in_hours},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 0:
        print(f"[热榜] API error: {data.get('msg', 'unknown error')}")
        return []

    return data.get("data", {}).get("list", [])


def search_global(query: str, count: int = 10) -> list[dict]:
    """全网可信搜 (API 3)。"""
    global _last_search_time
    with _search_lock:
        now = time.time()
        elapsed = now - _last_search_time
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        _last_search_time = time.time()

    headers = _generate_sign_headers()
    resp = httpx.get(
        f"{ZHIHU_OPENAPI_BASE}/openapi/search/global",
        params={"query": query, "count": min(count, 20)},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 0:
        print(f"[可信搜] API error: {data.get('msg', 'unknown error')}")
        return []

    return data.get("data", {}).get("items", [])


def search_credible_formatted(query: str, count: int = 5) -> str:
    """可信搜格式化输出 — 供裁判引用。"""
    if not ZHIHU_APP_KEY or not ZHIHU_APP_SECRET:
        return ""

    try:
        items = search_global(query, count=count)
        if not items:
            return ""

        results = []
        for item in items[:count]:
            author = item.get("author_name", "匿名")
            badge = item.get("author_badge_text", "")
            author_info = f"@{author}" + (f"({badge})" if badge else "")
            votes = item.get("vote_up_count", 0)
            title = item.get("title", "")
            text = (item.get("content_text", "") or "")[:200]

            line = f"- {author_info}（{votes}赞）：{title}"
            if text:
                line += f"\n  摘要：{text}"

            comments = item.get("comment_info_list", [])
            if comments:
                top_comment = comments[0].get("content", "")[:100]
                if top_comment:
                    line += f"\n  热评：{top_comment}"

            results.append(line)

        return "\n".join(results)
    except Exception as e:
        print(f"[可信搜] Error: {e}")
        return ""


def _search_topics_by_keywords(keywords: list[str], per_keyword: int = 5) -> list[dict]:
    """用可信搜按关键词搜索更多话题。"""
    if not ZHIHU_APP_KEY or not ZHIHU_APP_SECRET:
        return []

    topics = []
    seen_titles: set[str] = set()

    for kw in keywords:
        try:
            time.sleep(1.1)  # 1 QPS 限制
            items = search_global(kw, count=per_keyword)
            for item in items:
                title = item.get("title", "")
                if not title or title in seen_titles:
                    continue
                # 只取问答类型的，适合做辩论
                if item.get("content_type") not in ("Question", "Answer", "Article"):
                    continue
                seen_titles.add(title)
                body = (item.get("content_text", "") or "")[:200]
                topics.append({
                    "title": title,
                    "detail_text": body,
                    "question_token": item.get("content_id", ""),
                })
        except Exception as e:
            print(f"[可信搜补充] {kw} error: {e}")

    print(f"[可信搜补充] 搜索 {len(keywords)} 个关键词，获得 {len(topics)} 条话题")
    return topics


# 敏感词过滤 — 跳过政治敏感话题
SENSITIVE_KEYWORDS = [
    "美国", "美以", "以色列", "伊朗", "俄罗斯", "乌克兰", "台湾", "台海",
    "军事", "战争", "袭击", "轰炸", "导弹", "核武", "制裁", "间谍",
    "抗议", "示威", "暴动", "镇压", "维权",
    "习近平", "拜登", "特朗普", "普京", "泽连斯基",
    "共产党", "民主党", "共和党", "国防部", "外交部",
    "领土", "主权", "统一", "独立", "分裂",
    "六四", "天安门", "法轮功", "达赖",
    "NATO", "FBI", "CIA", "五眼联盟",
]


def _is_sensitive(title: str) -> bool:
    """检查标题是否包含敏感词。"""
    return any(kw in title for kw in SENSITIVE_KEYWORDS)


# 用于可信搜补充的安全关键词池
SEARCH_KEYWORDS = [
    "人工智能应用", "AI创业", "ChatGPT使用技巧", "科技产品评测",
    "职场经验", "面试技巧", "副业赚钱", "自由职业",
    "年轻人消费", "奶茶经济", "咖啡文化", "外卖行业",
    "考研经验", "留学生活", "大学生活", "毕业选择",
    "恋爱观", "婚姻观", "相亲", "社交焦虑",
    "健身", "减肥", "心理健康", "睡眠质量",
    "电影推荐", "游戏评测", "动漫", "综艺节目",
    "短视频运营", "自媒体", "直播带货", "小红书",
    "新能源汽车", "智能手机", "数码产品", "智能家居",
    "房价走势", "租房经验", "装修避坑", "城市选择",
    "宠物养育", "旅行攻略", "美食推荐", "穿搭",
    "编程学习", "转行IT", "远程办公", "创业失败",
]


def fetch_hotlist_for_debates(count: int = 20) -> list[dict]:
    """获取热榜+可信搜话题。多时间窗口合并去重+关键词搜索补充。"""
    if ZHIHU_APP_KEY and ZHIHU_APP_SECRET:
        try:
            # Step 1: 多时间窗口拉热榜
            all_items: dict[str, dict] = {}
            for hours in [48, 168, 720]:
                batch = fetch_billboard(top_cnt=200, publish_in_hours=hours)
                for item in batch:
                    title = item.get("title", "")
                    if title and title not in all_items:
                        all_items[title] = item

            import re
            def _clean(s: str) -> str:
                return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)

            topics = []
            for item in all_items.values():
                title = _clean(item.get("title", ""))
                if _is_sensitive(title):
                    continue
                body = _clean((item.get("body", "") or "")[:200])
                answers = item.get("answers", [])
                answer_summaries = []
                for ans in (answers or [])[:3]:
                    ans_body = _clean((ans.get("body", "") or "")[:300])
                    votes = ans.get("interaction_info", {}).get("vote_up_count", 0)
                    if ans_body:
                        answer_summaries.append(f"({votes}赞) {ans_body}")
                detail = body
                if answer_summaries:
                    detail += "\n高赞回答：\n" + "\n".join(answer_summaries)
                if title:
                    topics.append({
                        "title": title,
                        "detail_text": detail,
                        "question_token": item.get("token", ""),
                    })

            print(f"[热榜] 热榜合并 {len(topics)} 条")

            # Step 2: 如果不够，用可信搜补充
            if len(topics) < count:
                need = count - len(topics)
                # 随机选几个关键词搜索
                import random
                kw_sample = random.sample(SEARCH_KEYWORDS, min(need // 3 + 2, len(SEARCH_KEYWORDS)))
                extra = _search_topics_by_keywords(kw_sample, per_keyword=10)
                # 去重
                existing_titles = {t["title"] for t in topics}
                for t in extra:
                    if t["title"] not in existing_titles:
                        topics.append(t)
                        existing_titles.add(t["title"])

            print(f"[热榜] 最终 {len(topics)} 条话题")
            return topics[:count]
        except Exception as e:
            print(f"[热榜] OpenAPI error: {e}")

    # 回退：Cookie 方式
    from config import ZHIHU_COOKIE
    if ZHIHU_COOKIE and ZHIHU_COOKIE != "your-zhihu-cookie-here":
        try:
            resp = httpx.get(
                "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
                params={"limit": count},
                headers={
                    "Cookie": ZHIHU_COOKIE,
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                topics = []
                for item in data.get("data", [])[:count]:
                    target = item.get("target", {})
                    title = target.get("title", "")
                    detail = target.get("excerpt", "")[:200]
                    if title:
                        topics.append({"title": title, "detail_text": detail})
                if topics:
                    return topics
        except Exception as e:
            print(f"[热榜] Cookie scrape error: {e}")

    print("[热榜] No hotlist data available")
    return []


def publish_to_zhihu_circle(content: str, ring_id: str = "2001009660925334090") -> dict | None:
    """发布想法到知乎圈子 (API 1B)。

    将获胜论点发布到知乎圈子，实现"观点出圈"。
    当前支持的圈子ID：2001009660925334090 和 2015023739549529606

    Args:
        content: 想法内容
        ring_id: 圈子 ID

    Returns:
        发布结果 dict，失败返回 None
    """
    if not ZHIHU_APP_KEY or not ZHIHU_APP_SECRET:
        print("[观点出圈] 缺少知乎 API 凭证")
        return None

    try:
        headers = _generate_sign_headers()
        headers["Content-Type"] = "application/json"

        resp = httpx.post(
            f"{ZHIHU_OPENAPI_BASE}/openapi/publish/pin",
            headers=headers,
            json={
                "ring_id": ring_id,
                "content": content,
            },
            timeout=15,
        )

        data = resp.json()
        if data.get("status") == 0:
            print(f"[观点出圈] 发布成功: {content[:50]}...")
            return data.get("data", {})
        else:
            print(f"[观点出圈] 发布失败: {data.get('msg', 'unknown error')}")
            return None
    except Exception as e:
        print(f"[观点出圈] Error: {e}")
        return None
