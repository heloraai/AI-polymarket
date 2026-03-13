"""ZhihuMarket — AI 预测市场 × 知乎群体智慧 (Demo 入口)

运行模式：
  python app.py              → 标准模式（热榜 → 舆情 → 交易）
  python app.py --deep       → 深度研究模式（多维信息采集 → 综合研判 → 交易）
  python app.py --hot-search → 热搜发现模式（从热搜词条发现突发预测机会）
"""

import asyncio
import sys

from config import ANTHROPIC_API_KEY, ZHIHU_COOKIE
from zhihu.client import ZhihuClient
from agents import (
    TopicHunterAgent,
    SentimentAnalystAgent,
    PredictionTraderAgent,
    OutcomeJudgeAgent,
    ZhihuResearcherAgent,
)


async def run_pipeline():
    """标准模式：热榜 → 舆情 → 交易"""
    zhihu = ZhihuClient(cookie=ZHIHU_COOKIE)

    try:
        # Step 1: 热点猎手扫描知乎热榜
        print("=" * 60)
        print("🔍 Step 1: 扫描知乎热榜，发现可预测事件...")
        print("=" * 60)

        hunter = TopicHunterAgent(zhihu, ANTHROPIC_API_KEY)
        markets = await hunter.scan_hotlist()
        print(f"\n发现 {len(markets)} 个可预测事件：")
        for m in markets:
            print(f"  [{m.category}] {m.title} (初始概率: {m.yes_probability:.0%})")

        if not markets:
            print("未发现适合的预测市场。")
            return

        # Step 2: 舆情分析
        print("\n" + "=" * 60)
        print("📊 Step 2: 分析知乎舆情...")
        print("=" * 60)

        analyst = SentimentAnalystAgent(zhihu, ANTHROPIC_API_KEY)
        sentiments = {}
        for market in markets[:3]:  # Demo 只分析前3个
            report = await analyst.analyze_question(market.source_question_id)
            sentiments[market.id] = report
            print(f"\n  [{market.title}]")
            print(f"    正面: {report.positive_ratio:.0%} | 负面: {report.negative_ratio:.0%}")
            print(f"    趋势: {report.sentiment_trend} | 置信度: {report.confidence:.0%}")
            if report.key_arguments_for:
                print(f"    正方论据: {report.key_arguments_for[0]}")
            if report.key_arguments_against:
                print(f"    反方论据: {report.key_arguments_against[0]}")

        # Step 3: 预测交易
        print("\n" + "=" * 60)
        print("💰 Step 3: AI Agent 做出交易决策...")
        print("=" * 60)

        trader = PredictionTraderAgent(ANTHROPIC_API_KEY)
        trades = []
        for market in markets[:3]:
            if market.id in sentiments:
                trade = await trader.evaluate_and_trade(market, sentiments[market.id])
                if trade:
                    trades.append(trade)
                    print(f"\n  交易: {trade.direction.value} on [{market.title}]")
                    print(f"    金额: {trade.amount:.1f} | 推理: {trade.reasoning[:100]}...")
                else:
                    print(f"\n  跳过: [{market.title}] — 无交易机会")

        # 汇总
        print("\n" + "=" * 60)
        print("📈 汇总")
        print("=" * 60)
        print(f"  扫描市场数: {len(markets)}")
        print(f"  分析舆情数: {len(sentiments)}")
        print(f"  执行交易数: {len(trades)}")
        print(f"  账户余额: {trader.portfolio.balance:.1f}")

    finally:
        await zhihu.close()


async def run_deep_research_pipeline():
    """深度研究模式：多维信息采集 → 综合研判 → 交易

    与标准模式的区别：
    - 标准模式：1个问题 × 20条回答 → 情绪分析
    - 深度模式：N个问题 × 回答 + 评论 + 搜索补充 → 综合研判

    信息采集维度：
    1. 源问题的回答（专家分析）
    2. 高赞回答的评论（即时情绪脉搏）
    3. 相关问题的回答（扩展视野）
    4. 主动搜索的补充信息（填补盲点）
    """
    zhihu = ZhihuClient(cookie=ZHIHU_COOKIE)

    try:
        # Step 1: 热点发现
        print("=" * 60)
        print("🔍 Step 1: 扫描知乎热榜，发现可预测事件...")
        print("=" * 60)

        hunter = TopicHunterAgent(zhihu, ANTHROPIC_API_KEY)
        markets = await hunter.scan_hotlist()
        print(f"\n发现 {len(markets)} 个可预测事件")

        if not markets:
            print("未发现适合的预测市场。")
            return

        for m in markets:
            print(f"  [{m.category}] {m.title}")

        # Step 2: 深度研究（替代简单的舆情分析）
        print("\n" + "=" * 60)
        print("🔬 Step 2: 深度研究（多维信息采集 + 综合研判）...")
        print("=" * 60)

        researcher = ZhihuResearcherAgent(zhihu, ANTHROPIC_API_KEY)
        briefs = {}

        for market in markets[:3]:
            # 从预测命题提取搜索关键词
            keywords = [market.source_question_title[:20]]

            brief = await researcher.research(
                prediction_title=market.title,
                source_question_id=market.source_question_id,
                search_keywords=keywords,
            )
            briefs[market.id] = brief

            print(f"\n  📋 [{market.title}]")
            print(f"    信息覆盖: {brief.questions_analyzed} 问题 / "
                  f"{brief.answers_analyzed} 回答 / {brief.comments_analyzed} 评论")
            print(f"    概率估计: {brief.probability_estimate:.0%} "
                  f"(置信度: {brief.confidence:.0%})")
            print(f"    情绪轨迹: {brief.sentiment_trajectory}")
            print(f"    信息完备性: {brief.information_completeness:.0%}")

            if brief.arguments_for:
                top_for = brief.arguments_for[0]
                print(f"    正方最强论据: [{top_for.get('evidence_strength', '?')}] "
                      f"{top_for.get('argument', '')[:80]}")
            if brief.arguments_against:
                top_against = brief.arguments_against[0]
                print(f"    反方最强论据: [{top_against.get('evidence_strength', '?')}] "
                      f"{top_against.get('argument', '')[:80]}")
            if brief.kol_opinions:
                kol = brief.kol_opinions[0]
                print(f"    KOL 观点: {kol.get('name', '?')} "
                      f"({kol.get('headline', '?')}) → {kol.get('stance', '?')}")
            if brief.key_uncertainties:
                print(f"    关键不确定性: {brief.key_uncertainties[0]}")

            print(f"    综合研判: {brief.summary[:120]}")

        # Step 3: 基于深度研究做交易决策
        print("\n" + "=" * 60)
        print("💰 Step 3: 基于深度研究的交易决策...")
        print("=" * 60)

        trader = PredictionTraderAgent(ANTHROPIC_API_KEY)
        trades = []

        for market in markets[:3]:
            if market.id not in briefs:
                continue
            brief = briefs[market.id]

            # 用深度研究的概率估计更新市场概率
            # 只在研究置信度 > 50% 时才考虑交易
            if brief.confidence < 0.5:
                print(f"\n  跳过: [{market.title}] — 研究置信度不足 ({brief.confidence:.0%})")
                continue

            # 将 ResearchBrief 转换为 SentimentReport 以兼容 trader
            from market.models import SentimentReport
            sentiment = SentimentReport(
                question_id=market.source_question_id,
                question_title=market.source_question_title,
                total_answers_analyzed=brief.answers_analyzed,
                positive_ratio=brief.probability_estimate,
                negative_ratio=1 - brief.probability_estimate,
                neutral_ratio=0.0,
                confidence=brief.confidence,
                key_arguments_for=[
                    a.get("argument", "") for a in brief.arguments_for[:3]
                ],
                key_arguments_against=[
                    a.get("argument", "") for a in brief.arguments_against[:3]
                ],
                top_expert_opinions=[
                    f"{k.get('name', '?')}: {k.get('key_point', '')}"
                    for k in brief.kol_opinions[:3]
                ],
                sentiment_trend=(
                    "rising" if brief.sentiment_trajectory == "shifting_positive"
                    else "falling" if brief.sentiment_trajectory == "shifting_negative"
                    else "stable"
                ),
            )

            trade = await trader.evaluate_and_trade(market, sentiment)
            if trade:
                trades.append(trade)
                print(f"\n  交易: {trade.direction.value} on [{market.title}]")
                print(f"    金额: {trade.amount:.1f}")
                print(f"    推理: {trade.reasoning[:120]}...")
            else:
                print(f"\n  跳过: [{market.title}] — 无交易机会")

        # 汇总
        print("\n" + "=" * 60)
        print("📈 深度研究模式汇总")
        print("=" * 60)
        total_answers = sum(b.answers_analyzed for b in briefs.values())
        total_comments = sum(b.comments_analyzed for b in briefs.values())
        total_engagement = sum(b.total_engagement for b in briefs.values())
        print(f"  扫描市场数: {len(markets)}")
        print(f"  深度研究数: {len(briefs)}")
        print(f"  总分析回答: {total_answers}")
        print(f"  总分析评论: {total_comments}")
        print(f"  总互动量: {total_engagement}")
        print(f"  执行交易数: {len(trades)}")
        print(f"  账户余额: {trader.portfolio.balance:.1f}")

    finally:
        await zhihu.close()


async def run_hot_search_discovery():
    """热搜发现模式：从知乎热搜词条发现突发预测机会

    热搜与热榜的区别：
    - 热榜 = 已经有完整讨论的话题
    - 热搜 = 人们正在搜索的即时关注点，更敏感更即时

    is_new=True 的热搜词条代表突发事件，
    可能是预测市场的即时机会。
    """
    zhihu = ZhihuClient(cookie=ZHIHU_COOKIE)

    try:
        print("=" * 60)
        print("🔥 知乎热搜词条扫描")
        print("=" * 60)

        hot_searches = await zhihu.get_hot_search()
        print(f"\n发现 {len(hot_searches)} 个热搜词条：\n")

        for i, item in enumerate(hot_searches, 1):
            new_tag = " 🆕" if item.is_new else ""
            print(f"  {i:2d}. [{item.score:>8}] {item.display}{new_tag}")

        # 搜索新上榜的热搜词条对应的知乎问题
        new_items = [item for item in hot_searches if item.is_new]
        if new_items:
            print(f"\n发现 {len(new_items)} 个新上榜热搜，深入搜索...")
            for item in new_items[:3]:
                results = await zhihu.search(item.query, limit=3)
                if results:
                    print(f"\n  「{item.query}」相关问题：")
                    for r in results:
                        print(f"    → {r.title} (回答: {r.answer_count}, 关注: {r.follower_count})")
        else:
            print("\n暂无新上榜热搜。")

    finally:
        await zhihu.close()


if __name__ == "__main__":
    if "--deep" in sys.argv:
        asyncio.run(run_deep_research_pipeline())
    elif "--hot-search" in sys.argv:
        asyncio.run(run_hot_search_discovery())
    else:
        asyncio.run(run_pipeline())
