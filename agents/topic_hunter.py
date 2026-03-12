"""热点猎手 Agent — 从知乎热榜发现可预测事件并生成预测市场"""

import uuid
from datetime import datetime, timedelta

import anthropic

from zhihu.client import ZhihuClient, HotListItem
from market.models import PredictionMarket


SYSTEM_PROMPT = """\
你是一个预测市场的"热点猎手"。你的任务是从知乎热榜话题中发现可以创建预测市场的事件。

一个好的预测市场命题应该满足：
1. 有明确的 YES/NO 结果（二元结果）
2. 有明确的结算日期（可以验证）
3. 有争议性（不是一边倒的共识）
4. 与公众关注度高的话题相关

请从给定的热榜话题中：
1. 筛选出适合创建预测市场的话题
2. 为每个话题生成一个精准的预测命题
3. 建议结算日期
4. 分类（科技/娱乐/政治/经济/社会/体育）

输出 JSON 格式：
[
  {
    "source_title": "原始知乎问题标题",
    "source_question_id": "问题ID",
    "prediction_title": "预测命题（YES/NO格式）",
    "description": "详细描述",
    "category": "分类",
    "resolution_date": "YYYY-MM-DD",
    "initial_probability": 0.5,
    "reasoning": "为什么这是一个好的预测市场"
  }
]
"""


class TopicHunterAgent:
    """从知乎热榜中发现可预测事件"""

    def __init__(self, zhihu_client: ZhihuClient, anthropic_api_key: str):
        self.zhihu = zhihu_client
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    async def scan_hotlist(self) -> list[PredictionMarket]:
        """扫描知乎热榜，生成预测市场"""
        hot_items = await self.zhihu.get_hot_list(limit=50)

        # 用 LLM 分析哪些话题适合做预测市场
        hot_items_text = "\n".join(
            f"- [{item.question_id}] {item.title} (热度: {item.hot_score})\n  摘要: {item.excerpt}"
            for item in hot_items
        )

        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"以下是当前知乎热榜话题，请筛选并生成预测市场：\n\n{hot_items_text}",
            }],
        )

        # 解析 LLM 输出，创建预测市场
        import json
        content = response.content[0].text

        # 提取 JSON 部分
        start = content.find("[")
        end = content.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        markets_data = json.loads(content[start:end])
        markets = []

        for m in markets_data:
            market = PredictionMarket(
                id=str(uuid.uuid4())[:8],
                title=m["prediction_title"],
                description=m.get("description", ""),
                source_question_id=m["source_question_id"],
                source_question_title=m["source_title"],
                category=m.get("category", "其他"),
                resolution_date=datetime.strptime(m["resolution_date"], "%Y-%m-%d")
                if m.get("resolution_date")
                else datetime.now() + timedelta(days=30),
                yes_probability=m.get("initial_probability", 0.5),
            )
            markets.append(market)

        return markets
