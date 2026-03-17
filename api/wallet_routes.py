"""观点交易所 — 钱包 API"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import INITIAL_USER_BALANCE
from services.wallet import (
    get_or_create_wallet, buy_shares, calculate_net_worth, get_portfolio,
)

wallet_router = APIRouter(prefix="/api/wallet")


class BuySharesRequest(BaseModel):
    debate_id: str
    option_key: str
    quantity: int = 1


@wallet_router.get("/{user_id}")
def get_wallet(user_id: str, user_name: str = ""):
    """获取或创建钱包，返回含观点身价。"""
    wallet = get_or_create_wallet(user_id, user_name)
    net_worth = calculate_net_worth(wallet)
    return {
        **wallet,
        "net_worth": net_worth,
        "initial_balance": wallet.get("initial_balance", INITIAL_USER_BALANCE),
        "total_pnl": round(net_worth - wallet.get("initial_balance", INITIAL_USER_BALANCE), 1),
    }


@wallet_router.post("/{user_id}/buy")
def buy_opinion_shares(user_id: str, req: BuySharesRequest):
    """买入观点股 = 参战。买入后自动触发辩论。"""
    try:
        wallet = buy_shares(user_id, req.debate_id, req.option_key, req.quantity)
        net_worth = calculate_net_worth(wallet)

        # Auto-run the debate in background after user joins
        import threading
        from services.persistence import load_debates
        from services.llm import get_deepseek_client
        from services.debate_engine import (
            run_phase1_roundtable, run_phase2_reveal_bet,
            run_phase3_team_defense, run_phase4_judgment,
        )
        from services.persistence import save_debate
        from agents.personalities import AGENT_PERSONALITIES

        debates = load_debates()
        debate = debates.get(req.debate_id)
        if debate and debate.get("status") == "created":
            def auto_run():
                try:
                    client = get_deepseek_client()
                    builtin_ids = {a["id"] for a in AGENT_PERSONALITIES}
                    agents = list(AGENT_PERSONALITIES)
                    for ca in debate.get("agents", []):
                        if ca["id"] not in builtin_ids:
                            agents.append({
                                "id": ca["id"], "name": ca["name"],
                                "emoji": ca.get("emoji", "\U0001f464"),
                                "description": ca.get("description", ""),
                                "risk_appetite": ca.get("risk_appetite", 0.5),
                                "system_prompt": ca.get("system_prompt",
                                    f"\u4f60\u662f{ca['name']}\uff0c\u4e00\u4e2a\u8fa9\u8bba\u53c2\u4e0e\u8005\u3002\u8bf7\u7528\u4e2d\u6587\u53d1\u8868\u4f60\u7684\u89c2\u70b9\u3002"),
                            })

                    debate["status"] = "running"
                    debate["phase"] = "\u5706\u684c\u8ba8\u8bba"
                    save_debate(debate)

                    transcript = run_phase1_roundtable(client, debate, agents)
                    debate["transcript"] = transcript
                    debate["phase"] = "\u4eae\u724c\u4e0b\u6ce8"
                    save_debate(debate)

                    bets, market_prices = run_phase2_reveal_bet(client, debate, agents, transcript)
                    debate["bets"] = bets
                    debate["market_prices"] = market_prices
                    debate["phase"] = "\u7ad9\u961f\u8fa9\u62a4"
                    save_debate(debate)

                    defense_messages = run_phase3_team_defense(client, debate, agents, transcript, bets)
                    debate["team_defense_messages"] = defense_messages
                    for msg in defense_messages:
                        transcript.append(msg)
                    debate["transcript"] = transcript
                    debate["phase"] = "\u5218\u770b\u5c71\u88c1\u51b3"
                    save_debate(debate)

                    judgment = run_phase4_judgment(client, debate, transcript, bets, defense_messages)
                    debate["judgment"] = judgment
                    debate["payouts"] = judgment["payouts"]
                    debate["status"] = "completed"
                    debate["phase"] = "\u5df2\u7ed3\u675f"
                    save_debate(debate)

                    # Settle wallets
                    from services.wallet import settle_holdings_for_debate
                    settle_holdings_for_debate(req.debate_id)

                    # Post to Zhihu
                    try:
                        from services.zhihu_api import publish_to_zhihu_circle
                        from datetime import datetime as dt
                        winning_label = judgment.get("winning_label", "")
                        mvp = judgment.get("mvp", "")
                        mvp_argument = ""
                        for msg in transcript:
                            if msg.get("agent_name") == mvp and msg.get("phase", "").startswith("\u5706\u684c\u8ba8\u8bba"):
                                mvp_argument = msg.get("content", "")[:200]
                                break
                        post_content = (
                            f"\u3010\u89c2\u70b9\u4ea4\u6613\u6240 \u00b7 AI\u8fa9\u8bba\u901f\u62a5\u3011\n\n"
                            f"\U0001f4cc \u8fa9\u9898\uff1a{debate['title']}\n\n"
                            f"\U0001f3c6 \u80dc\u51fa\u89c2\u70b9\uff1a{winning_label}\n"
                            f"\u2b50 MVP\uff1a{mvp}\n\n"
                            f"\U0001f4ac \u6838\u5fc3\u8bba\u70b9\uff1a{mvp_argument or judgment.get('reasoning', '')[:200]}\n\n"
                            f"\U0001f449 \u6765\u89c2\u70b9\u4ea4\u6613\u6240\uff0c\u7528\u79ef\u5206\u4e3a\u4f60\u7684\u89c2\u70b9\u4e0b\u6ce8\n"
                            f"https://reconnect-hackathon.com/projects/cmmtbrbth000604jut32hadex\n\n"
                            f"#\u89c2\u70b9\u4ea4\u6613\u6240 #AI\u8fa9\u8bba #\u77e5\u4e4e\u70ed\u699c"
                        )
                        result = publish_to_zhihu_circle(post_content)
                        if result:
                            debate["zhihu_post"] = {
                                "published": True,
                                "post_id": result.get("content_token", ""),
                                "content": post_content,
                                "published_at": dt.now().isoformat(),
                            }
                            save_debate(debate)
                    except Exception as e:
                        print(f"[\u89c2\u70b9\u51fa\u5708] Failed: {e}")

                    print(f"[AUTO-RUN] Debate {req.debate_id} completed: {judgment.get('winning_label')}")
                except Exception as e:
                    print(f"[AUTO-RUN] Error: {e}")
                    debate["status"] = "created"
                    save_debate(debate)

            t = threading.Thread(target=auto_run, daemon=True)
            t.start()

        return {
            "message": f"\u6210\u529f\u4e70\u5165\uff0c\u8fa9\u8bba\u5373\u5c06\u81ea\u52a8\u5f00\u59cb",
            "wallet": {**wallet, "net_worth": net_worth},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@wallet_router.get("/{user_id}/portfolio")
def get_user_portfolio(user_id: str):
    """获取持仓组合。"""
    portfolio = get_portfolio(user_id)
    return portfolio
