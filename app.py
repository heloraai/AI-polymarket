"""观点交易所 — CLI 竞技场模式

5 个性格迥异的 AI Agent 在知乎热榜话题上互相博弈：
  🐂 牛哥 — 永远看多的乐观主义者
  🐻 熊总 — 专业唱衰三十年
  🦊 狐师 — 永远和大众反着来
  🦉 鸮博士 — 数据驱动的冷静分析师
  🎲 梭哈王 — 高风险高回报的动量追随者

运行：
  python app.py           → 竞技场模式（默认）
  python app.py --settle  → 结算模式
"""

import asyncio
import sys

from config import ANTHROPIC_API_KEY, ZHIHU_COOKIE
from zhihu.client import ZhihuClient
from agents import TopicHunterAgent
from agents.arena import Arena


async def run_arena():
    """竞技场模式：Agent 对战"""
    zhihu = ZhihuClient(cookie=ZHIHU_COOKIE)

    try:
        print("=" * 60)
        print("  观点交易所 — AI Agent 对战预测市场")
        print("=" * 60)
        print("\n🔍 扫描知乎热榜，寻找战场...\n")

        hunter = TopicHunterAgent(zhihu, ANTHROPIC_API_KEY)
        markets = await hunter.scan_hotlist()

        if not markets:
            print("今天没有适合对战的话题。")
            return

        print(f"发现 {len(markets)} 个可对战话题：")
        for i, m in enumerate(markets, 1):
            print(f"  {i}. [{m.category}] {m.title}")

        arena = Arena(zhihu, ANTHROPIC_API_KEY)

        for market in markets[:3]:
            print(f"\n{'=' * 60}")
            print(f"  ⚔️  对战开始: {market.title}")
            print(f"{'=' * 60}")
            print(f"  初始 YES 价格: {market.yes_probability:.0%}\n")

            result = await arena.run_market(market)

            if not result.trades:
                print("  所有 Agent 都选择观望，没有交易发生。")
                continue

            print("  📜 交易记录：")
            for trade in result.trades:
                emoji = ""
                for p in arena.personalities:
                    if p.name == trade.agent_name:
                        emoji = p.emoji
                        break
                direction = "YES" if trade.direction.value == "buy_yes" else "NO"
                print(
                    f"    {emoji} {trade.agent_name:4s} → "
                    f"买 {direction:3s} ${trade.amount:6.0f} "
                    f"(信心: {trade.confidence:.0%})"
                )
                reasoning = trade.reasoning.replace("\n", " ")[:100]
                print(f"      💬 {reasoning}")

            print(f"\n  📈 价格轨迹：")
            price_bar = " → ".join(f"{p:.0%}" for p in result.price_history)
            print(f"    {price_bar}")

            final_price = result.price_history[-1]
            initial_price = result.price_history[0]
            delta = final_price - initial_price
            direction_word = "↑ 看涨" if delta > 0 else "↓ 看跌" if delta < 0 else "→ 持平"
            print(f"    最终价格: {final_price:.0%} ({direction_word} {abs(delta):.0%})")

        print(f"\n{'=' * 60}")
        print("  🏆 Agent 排行榜")
        print(f"{'=' * 60}")
        for i, portfolio in enumerate(result.leaderboard, 1):
            emoji = ""
            for p in arena.personalities:
                if p.name == portfolio.agent_name:
                    emoji = p.emoji
                    break
            trades_count = sum(
                len(pos) for pos in portfolio.positions.values()
                if isinstance(pos, list)
            )
            status = "💤 观望中" if trades_count == 0 else f"📊 {trades_count} 笔交易"
            print(
                f"  {i}. {emoji} {portfolio.agent_name:4s} "
                f"| 余额: ${portfolio.balance:7.0f} "
                f"| {status}"
            )

        print(f"\n💡 提示: 运行 `python app.py --settle` 可在事件结算后计算盈亏")

    finally:
        await zhihu.close()


async def run_settle():
    """结算模式"""
    print("⚖️  结算模式尚未实现 — 需要等待预测事件到期后由裁判裁定。")


if __name__ == "__main__":
    if "--settle" in sys.argv:
        asyncio.run(run_settle())
    else:
        asyncio.run(run_arena())
