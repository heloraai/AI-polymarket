"""观点货币系统 — 观点钱包

每个用户有一个观点钱包：
- balance: 可用积分余额
- holdings: 观点股持仓（买入的观点）
- transactions: 交易记录

观点 = 货币。好观点升值，烂观点归零。
"""

import uuid
from datetime import datetime

from config import INITIAL_USER_BALANCE, SHARE_PAYOUT
from services.persistence import load_wallets, save_wallet, load_debates
from services.pricing import calculate_option_prices


def get_or_create_wallet(user_id: str, user_name: str = "") -> dict:
    """获取或创建用户钱包。"""
    wallets = load_wallets()
    if user_id in wallets:
        wallet = wallets[user_id]
        # 修复旧钱包：如果没有 initial_balance，用当前余额作为基准
        if "initial_balance" not in wallet:
            wallet["initial_balance"] = wallet.get("balance", INITIAL_USER_BALANCE)
            save_wallet(wallet)
        return wallet

    wallet = {
        "user_id": user_id,
        "user_name": user_name or f"交易员_{user_id[:6]}",
        "balance": INITIAL_USER_BALANCE,
        "initial_balance": INITIAL_USER_BALANCE,
        "created_at": datetime.now().isoformat(),
        "holdings": [],
        "transactions": [],
    }
    save_wallet(wallet)
    return wallet


def buy_shares(
    user_id: str,
    debate_id: str,
    option_key: str,
    quantity: int = 1,
) -> dict:
    """买入观点股。

    Returns updated wallet dict.
    Raises ValueError if insufficient balance or invalid params.
    """
    wallets = load_wallets()
    wallet = wallets.get(user_id)
    if not wallet:
        # 自动创建钱包
        wallet = get_or_create_wallet(user_id)
        wallets = load_wallets()

    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate:
        raise ValueError("辩论不存在")

    if debate.get("status") not in ("created", "running"):
        raise ValueError("辩论已结束，无法买入")

    # Check if user already has a holding in this debate
    for h in wallet.get("holdings", []):
        if h["debate_id"] == debate_id and h["status"] == "active":
            raise ValueError("你已经在这场辩论中买入了观点，不能重复买入")

    # Find option
    options = debate.get("options", [])
    option = next((o for o in options if o["key"] == option_key), None)
    if not option:
        raise ValueError(f"选项 {option_key} 不存在")

    quantity = 1  # 每个观点只能买入1份

    # Get current price
    option_keys = [o["key"] for o in options]
    prices = calculate_option_prices(
        option_keys, debate.get("bets", []), seed=debate["title"]
    )
    price_per_share = prices.get(option_key, 50.0)

    total_cost = round(price_per_share * quantity, 1)

    if wallet["balance"] < total_cost:
        raise ValueError(
            f"余额不足：需要 {total_cost} 积分，当前余额 {wallet['balance']} 积分"
        )

    # Deduct balance
    wallet["balance"] = round(wallet["balance"] - total_cost, 1)

    # Add holding
    holding = {
        "id": f"h_{uuid.uuid4().hex[:8]}",
        "debate_id": debate_id,
        "debate_title": debate["title"],
        "option_key": option_key,
        "option_label": option["label"],
        "quantity": quantity,
        "buy_price": price_per_share,
        "total_cost": total_cost,
        "status": "active",
        "bought_at": datetime.now().isoformat(),
    }
    wallet["holdings"].append(holding)

    # Add transaction
    wallet["transactions"].append({
        "id": f"tx_{uuid.uuid4().hex[:8]}",
        "type": "buy",
        "debate_id": debate_id,
        "option_label": option["label"],
        "amount": -total_cost,
        "shares": quantity,
        "price_per_share": price_per_share,
        "timestamp": datetime.now().isoformat(),
    })

    save_wallet(wallet)
    return wallet


def settle_holdings_for_debate(debate_id: str) -> None:
    """结算某场辩论的所有用户持仓。

    获胜观点持有者获得 SHARE_PAYOUT (100) * quantity 积分。
    失败观点持有者损失全部投入。
    """
    debates = load_debates()
    debate = debates.get(debate_id)
    if not debate or debate.get("status") != "completed":
        return

    judgment = debate.get("judgment")
    if not judgment:
        return

    winning_option = judgment.get("winning_option", "")

    wallets = load_wallets()
    changed = False

    for wallet in wallets.values():
        for holding in wallet.get("holdings", []):
            if holding["debate_id"] != debate_id:
                continue
            if holding["status"] != "active":
                continue

            is_win = holding["option_key"] == winning_option
            payout = SHARE_PAYOUT * holding["quantity"] if is_win else 0

            holding["status"] = "settled_win" if is_win else "settled_lose"

            if is_win:
                wallet["balance"] = round(wallet["balance"] + payout, 1)

            wallet["transactions"].append({
                "id": f"tx_{uuid.uuid4().hex[:8]}",
                "type": "settle_win" if is_win else "settle_lose",
                "debate_id": debate_id,
                "option_label": holding["option_label"],
                "amount": payout if is_win else -holding["total_cost"],
                "shares": holding["quantity"],
                "price_per_share": SHARE_PAYOUT if is_win else 0,
                "timestamp": datetime.now().isoformat(),
            })

            changed = True

    if changed:
        from services.persistence import save_wallets
        save_wallets(wallets)


def calculate_net_worth(wallet: dict) -> float:
    """计算观点身价 = 余额 + 持仓市值。"""
    balance = wallet.get("balance", 0)
    debates = load_debates()

    holdings_value = 0.0
    for holding in wallet.get("holdings", []):
        if holding["status"] != "active":
            continue

        debate = debates.get(holding["debate_id"])
        if not debate:
            continue

        options = debate.get("options", [])
        option_keys = [o["key"] for o in options]
        prices = calculate_option_prices(
            option_keys, debate.get("bets", []), seed=debate["title"]
        )
        current_price = prices.get(holding["option_key"], 0)
        holdings_value += current_price * holding["quantity"]

    return round(balance + holdings_value, 1)


def get_portfolio(user_id: str) -> dict:
    """获取用户持仓组合。"""
    wallets = load_wallets()
    wallet = wallets.get(user_id)
    if not wallet:
        return {"active": [], "settled": [], "summary": {}}

    debates = load_debates()
    active = []
    settled = []

    total_invested = 0.0
    total_current_value = 0.0
    total_realized_pnl = 0.0

    for holding in wallet.get("holdings", []):
        debate = debates.get(holding["debate_id"])

        if holding["status"] == "active":
            current_price = 0.0
            if debate:
                options = debate.get("options", [])
                option_keys = [o["key"] for o in options]
                prices = calculate_option_prices(
                    option_keys, debate.get("bets", []), seed=debate["title"]
                )
                current_price = prices.get(holding["option_key"], 0)

            current_value = round(current_price * holding["quantity"], 1)
            pnl = round(current_value - holding["total_cost"], 1)
            pnl_pct = round(pnl / holding["total_cost"] * 100, 1) if holding["total_cost"] > 0 else 0

            active.append({
                **holding,
                "current_price": current_price,
                "current_value": current_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "debate_status": debate.get("status", "unknown") if debate else "unknown",
            })

            total_invested += holding["total_cost"]
            total_current_value += current_value
        else:
            pnl = 0.0
            if holding["status"] == "settled_win":
                pnl = round(SHARE_PAYOUT * holding["quantity"] - holding["total_cost"], 1)
            else:
                pnl = -holding["total_cost"]

            settled.append({
                **holding,
                "pnl": pnl,
                "result": "win" if holding["status"] == "settled_win" else "lose",
            })
            total_realized_pnl += pnl

    return {
        "active": active,
        "settled": settled,
        "summary": {
            "total_invested": round(total_invested, 1),
            "total_current_value": round(total_current_value, 1),
            "unrealized_pnl": round(total_current_value - total_invested, 1),
            "realized_pnl": round(total_realized_pnl, 1),
        },
    }
