"""舆情分析 Agent — 深度分析知乎回答中的多方观点"""

import anthropic

from zhihu.client import ZhihuClient
from market.models import SentimentReport


SYSTEM_PROMPT = """\
你是一个专业的舆情分析师。你的任务是分析知乎问题下的回答，提取多方观点并评估舆论方向。

对于给定的问题和回答，请分析：
1. 正面/负面/中性观点的比例
2. 正方的核心论据（最多3个）
3. 反方的核心论据（最多3个）
4. 高可信度答主的关键观点
5. 舆论趋势：是否有明显的方向性

评估可信度时考虑：
- 答主是否有相关领域专业背景
- 论据是否有数据/事实支撑
- 回答的投票数和评论数

输出 JSON 格式：
{
  "positive_ratio": 0.0-1.0,
  "negative_ratio": 0.0-1.0,
  "neutral_ratio": 0.0-1.0,
  "confidence": 0.0-1.0,
  "key_arguments_for": ["论据1", "论据2"],
  "key_arguments_against": ["论据1", "论据2"],
  "top_expert_opinions": ["专家观点1"],
  "sentiment_trend": "rising|falling|stable",
  "summary": "一句话总结"
}
"""


class SentimentAnalystAgent:
    """分析知乎回答中的舆情"""

    def __init__(self, zhihu_client: ZhihuClient, anthropic_api_key: str):
        self.zhihu = zhihu_client
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    async def analyze_question(self, question_id: str) -> SentimentReport:
        """分析某个知乎问题下的舆情"""
        # 获取问题详情
        question = await self.zhihu.get_question(question_id)

        # 获取高赞回答
        answers = await self.zhihu.get_answers(question_id, limit=20, sort_by="default")

        # 构建分析输入
        answers_text = "\n\n".join(
            f"--- 回答 by {a.author_name} (赞同: {a.voteup_count}, 评论: {a.comment_count}) ---\n"
            f"{a.content[:2000]}"
            for a in answers
        )

        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"问题：{question.title}\n"
                    f"关注人数：{question.follower_count}\n"
                    f"回答数：{question.answer_count}\n\n"
                    f"以下是部分高赞回答：\n\n{answers_text}"
                ),
            }],
        )

        # 解析结果
        import json
        content = response.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            # 返回默认报告
            return SentimentReport(
                question_id=question_id,
                question_title=question.title,
                total_answers_analyzed=len(answers),
                positive_ratio=0.5,
                negative_ratio=0.3,
                neutral_ratio=0.2,
                confidence=0.3,
            )

        data = json.loads(content[start:end])

        return SentimentReport(
            question_id=question_id,
            question_title=question.title,
            total_answers_analyzed=len(answers),
            positive_ratio=data.get("positive_ratio", 0.5),
            negative_ratio=data.get("negative_ratio", 0.3),
            neutral_ratio=data.get("neutral_ratio", 0.2),
            confidence=data.get("confidence", 0.5),
            key_arguments_for=data.get("key_arguments_for", []),
            key_arguments_against=data.get("key_arguments_against", []),
            top_expert_opinions=data.get("top_expert_opinions", []),
            sentiment_trend=data.get("sentiment_trend", "stable"),
        )
