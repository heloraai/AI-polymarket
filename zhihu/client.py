"""知乎 API 客户端 — 获取热榜、问题、回答等数据"""

import httpx
from dataclasses import dataclass


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


@dataclass
class HotListItem:
    title: str
    url: str
    hot_score: int
    excerpt: str
    question_id: str


class ZhihuClient:
    """知乎数据客户端（基于非官方 API v4）"""

    BASE_URL = "https://www.zhihu.com/api/v4"
    HOTLIST_URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"

    def __init__(self, cookie: str = ""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.zhihu.com/",
        }
        if cookie:
            self.headers["Cookie"] = cookie
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)

    async def get_hot_list(self, limit: int = 50) -> list[HotListItem]:
        """获取知乎热榜"""
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

    async def get_question(self, question_id: str) -> ZhihuQuestion:
        """获取问题详情"""
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
        """获取问题下的回答（按默认排序/投票排序）"""
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
            ))
        return answers

    async def close(self):
        await self.client.aclose()
