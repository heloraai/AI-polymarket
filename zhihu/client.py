"""知乎 API 客户端 — 获取热榜、搜索、问题、回答、评论等多维数据

知乎作为预测市场信息源的独特价值：
- 热榜/热搜 = 社会关注度信号（什么事情值得预测）
- 回答 = 分布式专家分析（正反方论据 + 数据支撑）
- 评论 = 实时情绪脉搏（比回答更即时的群体反应）
- 搜索 = 主动信息获取（不只被动等热榜推送）
- 话题 = 领域聚合（追踪特定赛道的趋势演变）
- 作者画像 = 专家可信度加权（大V vs 匿名用户的信号差异）

所有端点均基于知乎非官方 API v4，需要 Cookie 认证以获得更高的请求限额。
"""

import re
import httpx
from dataclasses import dataclass, field


@dataclass
class ZhihuQuestion:
    id: str
    title: str
    url: str
    answer_count: int
    follower_count: int
    excerpt: str = ""


@dataclass
class ZhihuAnswer:
    id: str
    question_id: str
    author_name: str
    content: str
    voteup_count: int
    comment_count: int
    created_time: int
    author_headline: str = ""       # 作者一句话介绍（用于判断专业背景）
    author_follower_count: int = 0  # 作者粉丝数（影响力指标）


@dataclass
class HotListItem:
    title: str
    url: str
    hot_score: int
    excerpt: str
    question_id: str


@dataclass
class HotSearchItem:
    """知乎热搜词条 — 比热榜更即时的趋势信号"""
    query: str          # 搜索词
    display: str        # 展示文案
    score: int          # 热度分数
    is_new: bool        # 是否新上榜（突发事件指标）


@dataclass
class SearchResult:
    """搜索结果 — 主动获取特定话题的信息"""
    question_id: str
    title: str
    excerpt: str
    answer_count: int
    follower_count: int
    relevance_score: float = 0.0


@dataclass
class Comment:
    """回答下的评论 — 最即时的群体情绪信号"""
    id: str
    author_name: str
    content: str
    like_count: int
    created_time: int
    reply_count: int = 0


@dataclass
class TopicInfo:
    """知乎话题 — 领域级别的信息聚合"""
    id: str
    name: str
    follower_count: int
    questions_count: int
    description: str = ""


def _strip_html(html: str) -> str:
    """去除 HTML 标签，保留纯文本"""
    text = re.sub(r"<[^>]+>", "", html)
    return text.strip()


class ZhihuClient:
    """知乎数据客户端（基于非官方 API v4）

    设计理念：为预测市场 Agent 提供多维信息采集能力。
    不同端点对应不同的信息价值：

    被动发现（Push）:
        get_hot_list()    → 当前社会焦点，用于发现预测市场选题
        get_hot_search()  → 即时搜索趋势，捕捉突发事件

    主动探索（Pull）:
        search()          → 针对特定话题搜索相关问题
        get_topic_feeds() → 追踪特定领域的精华内容

    深度分析（Depth）:
        get_question()    → 问题元数据（关注人数 = 市场关注度）
        get_answers()     → 专家分析 + 正反方论据
        get_comments()    → 实时情绪脉搏

    信号加权（Weight）:
        get_author_info() → 判断信息源可信度
    """

    BASE_URL = "https://www.zhihu.com/api/v4"
    HOTLIST_URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
    HOT_SEARCH_URL = "https://www.zhihu.com/api/v4/search/top_search"

    def __init__(self, cookie: str = ""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.zhihu.com/",
        }
        if cookie:
            self.headers["Cookie"] = cookie
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)

    # ── 被动发现：热榜 & 热搜 ──────────────────────────────

    async def get_hot_list(self, limit: int = 50) -> list[HotListItem]:
        """获取知乎热榜 — 社会关注度的晴雨表

        热榜话题的热度分代表了全社会的关注度分布。
        高热度 + 有争议性的话题 = 好的预测市场选题。
        """
        resp = await self.client.get(
            self.HOTLIST_URL, params={"limit": limit}
        )
        resp.raise_for_status()
        data = resp.json()

        items = []
        for item in data.get("data", []):
            target = item.get("target", {})
            items.append(HotListItem(
                title=target.get("title", ""),
                url=target.get("url", ""),
                hot_score=item.get("detail_text", "0"),
                excerpt=target.get("excerpt", ""),
                question_id=str(target.get("id", "")),
            ))
        return items

    async def get_hot_search(self) -> list[HotSearchItem]:
        """获取知乎热搜榜 — 比热榜更即时的趋势信号

        热搜反映的是"此刻人们在搜什么"，比热榜更敏感。
        is_new=True 的词条代表突发事件，可能是预测市场的即时机会。
        """
        resp = await self.client.get(self.HOT_SEARCH_URL)
        resp.raise_for_status()
        data = resp.json()

        items = []
        for item in data.get("data", []):
            items.append(HotSearchItem(
                query=item.get("query", ""),
                display=item.get("display", ""),
                score=item.get("score", 0),
                is_new=item.get("is_new", False),
            ))
        return items

    # ── 主动探索：搜索 & 话题 ──────────────────────────────

    async def search(
        self, query: str, limit: int = 10, search_type: str = "general"
    ) -> list[SearchResult]:
        """搜索知乎问题 — 主动获取特定话题的群体智慧

        与热榜的区别：热榜是"知乎推给你的"，搜索是"你主动去找的"。
        Agent 在分析一个预测市场时，可以用搜索补充热榜之外的相关问题，
        获得更全面的信息覆盖。

        search_type: "general" 综合搜索, "topic" 话题搜索
        """
        url = f"{self.BASE_URL}/search_v3"
        params = {
            "q": query,
            "t": search_type,
            "limit": limit,
            "offset": 0,
            "correction": 1,
        }
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("data", []):
            obj = item.get("object", {})
            # 只提取问题类型的结果
            if item.get("type") != "search_result" or obj.get("type") != "question":
                continue
            results.append(SearchResult(
                question_id=str(obj.get("id", "")),
                title=_strip_html(obj.get("title", "")),
                excerpt=_strip_html(obj.get("excerpt", "")),
                answer_count=obj.get("answer_count", 0),
                follower_count=obj.get("follower_count", 0),
            ))
        return results

    async def get_topic_feeds(
        self, topic_id: str, limit: int = 10
    ) -> list[SearchResult]:
        """获取话题下的精华内容 — 领域级别的信息聚合

        每个知乎话题是一个领域的信息中心。
        例如 topic_id="19550517" 是"人工智能"话题。
        追踪特定话题的精华内容可以发现该领域的趋势变化。
        """
        url = f"{self.BASE_URL}/topics/{topic_id}/feeds/essence"
        params = {"limit": limit, "offset": 0}
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("data", []):
            target = item.get("target", {})
            question = target.get("question", target)  # 有些是直接问题，有些嵌套
            results.append(SearchResult(
                question_id=str(question.get("id", "")),
                title=question.get("title", ""),
                excerpt=_strip_html(target.get("excerpt", "")),
                answer_count=question.get("answer_count", 0),
                follower_count=question.get("follower_count", 0),
            ))
        return results

    # ── 深度分析：问题 / 回答 / 评论 ─────────────────────

    async def get_question(self, question_id: str) -> ZhihuQuestion:
        """获取问题详情 — 元数据揭示市场关注度"""
        url = f"{self.BASE_URL}/questions/{question_id}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()

        return ZhihuQuestion(
            id=str(data["id"]),
            title=data["title"],
            url=f"https://www.zhihu.com/question/{data['id']}",
            answer_count=data.get("answer_count", 0),
            follower_count=data.get("follower_count", 0),
            excerpt=data.get("excerpt", ""),
        )

    async def get_answers(
        self, question_id: str, limit: int = 20, sort_by: str = "default"
    ) -> list[ZhihuAnswer]:
        """获取问题下的回答 — 分布式专家分析

        sort_by="default" 知乎算法排序（综合质量）
        sort_by="updated" 按更新时间（看最新观点）

        每个回答附带作者画像信息（headline, follower_count），
        用于信号加权：大V的观点 vs 匿名用户的观点权重不同。
        """
        url = f"{self.BASE_URL}/questions/{question_id}/answers"
        params = {
            "include": "content,voteup_count,comment_count",
            "limit": limit,
            "sort_by": sort_by,
        }
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        answers = []
        for item in data.get("data", []):
            author = item.get("author", {})
            answers.append(ZhihuAnswer(
                id=str(item["id"]),
                question_id=question_id,
                author_name=author.get("name", "匿名用户"),
                content=item.get("content", ""),
                voteup_count=item.get("voteup_count", 0),
                comment_count=item.get("comment_count", 0),
                created_time=item.get("created_time", 0),
                author_headline=author.get("headline", ""),
                author_follower_count=author.get("follower_count", 0),
            ))
        return answers

    async def get_comments(
        self, answer_id: str, limit: int = 20, order: str = "score"
    ) -> list[Comment]:
        """获取回答下的评论 — 最即时的群体情绪脉搏

        评论比回答更短、更即时、更情绪化。
        这是捕捉群体情绪转向的最佳信号源。

        order="score" 按热度（最具代表性的群体声音）
        order="ts"    按时间（最新的情绪变化）
        """
        url = f"{self.BASE_URL}/answers/{answer_id}/comments"
        params = {"limit": limit, "order": order, "status": "open"}
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        comments = []
        for item in data.get("data", []):
            author = item.get("author", {})
            comments.append(Comment(
                id=str(item.get("id", "")),
                author_name=author.get("name", "匿名用户"),
                content=item.get("content", ""),
                like_count=item.get("like_count", 0),
                created_time=item.get("created_time", 0),
                reply_count=item.get("reply_count", 0),
            ))
        return comments

    async def get_related_questions(
        self, question_id: str, limit: int = 5
    ) -> list[SearchResult]:
        """获取相关问题 — 扩展信息视野

        一个预测话题往往有多个相关问题从不同角度讨论。
        例如"房价会跌吗"可能关联"该不该现在买房"、"房产税何时落地"等。
        聚合相关问题能获得更全面的群体判断。
        """
        url = f"{self.BASE_URL}/questions/{question_id}/similar-questions"
        params = {"limit": limit}
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("data", []):
            results.append(SearchResult(
                question_id=str(item.get("id", "")),
                title=item.get("title", ""),
                excerpt=item.get("excerpt", ""),
                answer_count=item.get("answer_count", 0),
                follower_count=item.get("follower_count", 0),
            ))
        return results

    # ── 信号加权：作者可信度 ─────────────────────────────

    async def get_author_info(self, url_token: str) -> dict:
        """获取作者详细信息 — 判断信息源可信度

        知乎的独特优势在于答主往往有可追溯的专业背景。
        通过 headline（自我介绍）、follower_count（影响力）、
        answer_count（活跃度）等维度判断信源质量。

        高可信度信号：
        - headline 包含行业关键词（如 "XX公司工程师"）
        - 高粉丝数（>10k）+ 高获赞数
        - 在相关话题下有多个高赞回答

        返回原始 dict 以保留全部字段供 Agent 自行判断。
        """
        url = f"{self.BASE_URL}/members/{url_token}"
        params = {
            "include": "answer_count,articles_count,follower_count,"
                       "voteup_count,thanked_count,headline,description,"
                       "badge",
        }
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ── 生命周期 ──────────────────────────────────────────

    async def close(self):
        await self.client.aclose()
