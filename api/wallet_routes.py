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
        "initial_balance": INITIAL_USER_BALANCE,
        "total_pnl": round(net_worth - INITIAL_USER_BALANCE, 1),
    }


@wallet_router.post("/{user_id}/buy")
def buy_opinion_shares(user_id: str, req: BuySharesRequest):
    """买入观点股。"""
    try:
        wallet = buy_shares(user_id, req.debate_id, req.option_key, req.quantity)
        net_worth = calculate_net_worth(wallet)
        return {
            "message": f"成功买入 {req.quantity} 股",
            "wallet": {**wallet, "net_worth": net_worth},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@wallet_router.get("/{user_id}/portfolio")
def get_user_portfolio(user_id: str):
    """获取持仓组合。"""
    portfolio = get_portfolio(user_id)
    return portfolio
