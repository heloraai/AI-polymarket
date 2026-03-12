"""ZhihuMarket — AI 预测市场 × 知乎群体智慧 (Demo 入口)"""

import asyncio

from config import ANTHROPIC_API_KEY, ZHIHU_COOKIE
from zhihu.client import ZhihuClient
from agents import TopicHunterAgent, SentimentAnalystAgent, PredictionTraderAgent, OutcomeJudgeAgent


async def run_pipeline():
    """运行完整的预测市场 pipeline"""
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


if __name__ == "__main__":
    asyncio.run(run_pipeline())
