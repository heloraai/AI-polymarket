"""市场定价 — Polymarket 风格 CPMM"""

import hashlib


def calculate_option_prices(
    option_keys: list[str],
    bets_so_far: list[dict],
    seed: str = "",
) -> dict[str, float]:
    """Laplace-smoothed CPMM 定价。

    当没有下注时，基于 seed 生成差异化的初始价格，
    模拟真实市场中不同选项的初始赔率差异。
    """
    n_opts = len(option_keys)
    if n_opts == 0:
        return {}

    bet_counts: dict[str, int] = {key: 0 for key in option_keys}
    for bet in bets_so_far:
        chosen = bet.get("chosen_option", "")
        if chosen in bet_counts:
            bet_counts[chosen] += 1

    total_bets = sum(bet_counts.values())

    if total_bets == 0 and seed:
        # 无下注时生成差异化初始价格
        # 用 seed (通常是辩题 title) 做确定性随机偏移
        raw_weights = []
        for i, key in enumerate(option_keys):
            h = hashlib.md5(f"{seed}:{key}:{i}".encode()).hexdigest()
            weight = 1.0 + (int(h[:4], 16) % 40 - 20) / 100.0  # ±20% 偏移
            raw_weights.append(weight)

        total_weight = sum(raw_weights)
        return {
            key: round(raw_weights[i] / total_weight * 100, 1)
            for i, key in enumerate(option_keys)
        }

    return {
        key: round((bet_counts[key] + 1) / (total_bets + n_opts) * 100, 1)
        for key in option_keys
    }
