"""知乎深度研究 Agent — 多维信息采集 × LLM 综合研判

设计思路：
传统做法是"热榜 → 回答 → 情绪分析"，这是单维度的浅层分析。
ZhihuResearcher 做的是多维度的深度研判：

1. 广度扩展：搜索相关问题 + 关联话题，不局限于单个问题
2. 深度挖掘：回答 + 评论两层分析，评论是更即时的情绪信号
3. 信源加权：根据作者背景给不同观点加权
4. 时间维度：对比新旧回答/评论，捕捉观点变化趋势
5. 信息综合：LLM 将多源信息综合为结构化研究报告

这个 Agent 的输出比简单的 SentimentReport 更丰富，
它产出的是一份完整的"研究简报"，包含：
- 信息覆盖图谱（分析了哪些问题、多少回答、多少评论）
- 多方论据的证据强度评级
- 关键意见领袖（KOL）的立场图谱
- 群体情绪的时间演变
- 信息确定性评估（哪些结论是有共识的，哪些仍在争论）
"""

import json
from dataclasses import dataclass, field

import anthropic

from zhihu.client import ZhihuClient, _strip_html


@dataclass
class ResearchBrief:
    """多维研究简报 — 比 SentimentReport 更丰富的信息产出"""
    query: str                                  # 研究主题
    questions_analyzed: int                     # 分析的问题数
    answers_analyzed: int                       # 分析的回答数
    comments_analyzed: int                      # 分析的评论数

    # 核心判断
    probability_estimate: float                 # Agent 估计的概率 (0-1)
    confidence: float                           # 判断置信度 (0-1)
    information_completeness: float             # 信息完备性 (0-1)

    # 多方论据（附证据强度）
    arguments_for: list[dict] = field(default_factory=list)
    # [{"argument": "...", "evidence_strength": "strong/medium/weak", "source": "..."}]

    arguments_against: list[dict] = field(default_factory=list)

    # KOL 立场图谱
    kol_opinions: list[dict] = field(default_factory=list)
    # [{"name": "...", "headline": "...", "stance": "for/against/neutral", "key_point": "..."}]

    # 情绪趋势
    sentiment_trajectory: str = "stable"        # "shifting_positive" / "shifting_negative" / "stable" / "polarizing"

    # 关键不确定性
    key_uncertainties: list[str] = field(default_factory=list)

    # 综合摘要
    summary: str = ""

    # 原始数据统计
    total_engagement: int = 0                   # 总互动量（赞+评论+点赞）


RESEARCH_SYSTEM_PROMPT = """\
你是一个预测市场的深度研究员。你的工作不是简单做情绪分析，而是像对冲基金分析师一样做综合研判。

你会收到一个预测命题和来自知乎多个问题的回答、评论数据。你需要：

1. **概率估计**：基于所有证据，估计命题为 YES 的概率 (0-1)
2. **证据评级**：对每个论据评估证据强度 (strong/medium/weak)
   - strong: 有数据支撑、有行业背景的专业分析
   - medium: 逻辑自洽但缺乏硬数据
   - weak: 情绪表达、臆测、缺乏论据
3. **KOL 立场**：识别有专业背景的答主，记录他们的立场
4. **情绪轨迹**：对比不同时间的回答/评论，判断群体观点是否在转变
5. **不确定性**：指出哪些关键信息缺失，可能影响判断

输出 JSON 格式：
{
  "probability_estimate": 0.0-1.0,
  "confidence": 0.0-1.0,
  "information_completeness": 0.0-1.0,
  "arguments_for": [
    {"argument": "论据", "evidence_strength": "strong|medium|weak", "source": "来源"}
  ],
  "arguments_against": [
    {"argument": "论据", "evidence_strength": "strong|medium|weak", "source": "来源"}
  ],
  "kol_opinions": [
    {"name": "答主", "headline": "身份", "stance": "for|against|neutral", "key_point": "核心观点"}
  ],
  "sentiment_trajectory": "shifting_positive|shifting_negative|stable|polarizing",
  "key_uncertainties": ["不确定性1", "不确定性2"],
  "summary": "一段综合研判"
}
"""


class ZhihuResearcherAgent:
    """知乎深度研究 Agent — 多维信息采集 × LLM 综合研判"""

    def __init__(self, zhihu_client: ZhihuClient, anthropic_api_key: str):
        self.zhihu = zhihu_client
        self.llm = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    async def research(
        self,
        prediction_title: str,
        source_question_id: str,
        search_keywords: list[str] | None = None,
    ) -> ResearchBrief:
        """对一个预测命题进行多维度深度研究

        信息采集策略：
        1. 从源问题出发，获取回答 + 评论
        2. 搜索相关问题，扩展信息广度
        3. 获取相关问题的回答，交叉验证观点
        4. 汇总所有信息，交给 LLM 综合研判

        Args:
            prediction_title: 预测命题（YES/NO 格式）
            source_question_id: 来源知乎问题 ID
            search_keywords: 额外搜索关键词（可选）
        """
        all_data_blocks = []
        total_answers = 0
        total_comments = 0
        total_engagement = 0
        questions_analyzed = 0

        # ── 第1层：源问题的深度分析 ────────────────────
        source_answers = await self.zhihu.get_answers(
            source_question_id, limit=20, sort_by="default"
        )
        questions_analyzed += 1
        total_answers += len(source_answers)

        source_block = self._format_answers_block(
            "源问题回答", source_answers
        )
        all_data_blocks.append(source_block)

        # 获取 top 5 回答的评论（评论是更即时的情绪信号）
        for answer in source_answers[:5]:
            if answer.comment_count > 0:
                comments = await self.zhihu.get_comments(answer.id, limit=10)
                total_comments += len(comments)
                if comments:
                    comment_block = self._format_comments_block(
                        f"回答「{answer.content[:30]}...」的评论",
                        comments,
                    )
                    all_data_blocks.append(comment_block)
                    total_engagement += sum(c.like_count for c in comments)

        total_engagement += sum(
            a.voteup_count + a.comment_count for a in source_answers
        )

        # ── 第2层：相关问题扩展 ─────────────────────────
        related_questions = await self.zhihu.get_related_questions(
            source_question_id, limit=5
        )

        for rq in related_questions[:3]:  # 取前3个相关问题
            rq_answers = await self.zhihu.get_answers(
                rq.question_id, limit=10, sort_by="default"
            )
            if rq_answers:
                questions_analyzed += 1
                total_answers += len(rq_answers)
                block = self._format_answers_block(
                    f"相关问题「{rq.title}」的回答", rq_answers
                )
                all_data_blocks.append(block)
                total_engagement += sum(
                    a.voteup_count + a.comment_count for a in rq_answers
                )

        # ── 第3层：主动搜索补充 ─────────────────────────
        if search_keywords:
            for keyword in search_keywords[:2]:  # 最多2个额外关键词
                search_results = await self.zhihu.search(keyword, limit=5)
                for sr in search_results[:2]:  # 每个关键词取前2个结果
                    # 跳过已分析的问题
                    if sr.question_id == source_question_id:
                        continue
                    sr_answers = await self.zhihu.get_answers(
                        sr.question_id, limit=5, sort_by="default"
                    )
                    if sr_answers:
                        questions_analyzed += 1
                        total_answers += len(sr_answers)
                        block = self._format_answers_block(
                            f"搜索「{keyword}」→「{sr.title}」的回答",
                            sr_answers,
                        )
                        all_data_blocks.append(block)

        # ── 综合研判：LLM 分析所有采集到的数据 ──────────
        combined_data = "\n\n".join(all_data_blocks)

        # 截断以适应 token 限制
        if len(combined_data) > 30000:
            combined_data = combined_data[:30000] + "\n\n[... 数据已截断 ...]"

        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=RESEARCH_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"预测命题：{prediction_title}\n\n"
                    f"信息采集范围：{questions_analyzed} 个问题, "
                    f"{total_answers} 条回答, {total_comments} 条评论\n"
                    f"总互动量：{total_engagement}\n\n"
                    f"以下是采集到的多维数据：\n\n{combined_data}"
                ),
            }],
        )

        # 解析研究报告
        content = response.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1

        if start == -1 or end == 0:
            return ResearchBrief(
                query=prediction_title,
                questions_analyzed=questions_analyzed,
                answers_analyzed=total_answers,
                comments_analyzed=total_comments,
                probability_estimate=0.5,
                confidence=0.3,
                information_completeness=0.3,
                summary="LLM 未能生成结构化研究报告",
                total_engagement=total_engagement,
            )

        data = json.loads(content[start:end])

        return ResearchBrief(
            query=prediction_title,
            questions_analyzed=questions_analyzed,
            answers_analyzed=total_answers,
            comments_analyzed=total_comments,
            probability_estimate=data.get("probability_estimate", 0.5),
            confidence=data.get("confidence", 0.5),
            information_completeness=data.get("information_completeness", 0.5),
            arguments_for=data.get("arguments_for", []),
            arguments_against=data.get("arguments_against", []),
            kol_opinions=data.get("kol_opinions", []),
            sentiment_trajectory=data.get("sentiment_trajectory", "stable"),
            key_uncertainties=data.get("key_uncertainties", []),
            summary=data.get("summary", ""),
            total_engagement=total_engagement,
        )

    def _format_answers_block(
        self, section_title: str, answers: list
    ) -> str:
        """将回答列表格式化为 LLM 可读的文本块"""
        lines = [f"=== {section_title} ==="]
        for a in answers:
            author_info = a.author_name
            if a.author_headline:
                author_info += f" ({a.author_headline})"
            if a.author_follower_count > 1000:
                author_info += f" [粉丝: {a.author_follower_count}]"

            content = _strip_html(a.content)[:1500]
            lines.append(
                f"\n--- {author_info} | 赞同: {a.voteup_count} | 评论: {a.comment_count} ---\n"
                f"{content}"
            )
        return "\n".join(lines)

    def _format_comments_block(
        self, section_title: str, comments: list
    ) -> str:
        """将评论列表格式化为 LLM 可读的文本块"""
        lines = [f">>> {section_title}"]
        for c in comments:
            lines.append(
                f"  [{c.author_name}] (赞: {c.like_count}) {c.content}"
            )
        return "\n".join(lines)
