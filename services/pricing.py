"""市场定价 — Polymarket 风格 CPMM"""


def calculate_option_prices(
    option_keys: list[str],
    bets_so_far: list[dict],
) -> dict[str, float]:
    """Laplace-smoothed CPMM 定价。"""
    n_opts = len(option_keys)
    if n_opts == 0:
        return {}

    bet_counts: dict[str, int] = {key: 0 for key in option_keys}
    for bet in bets_so_far:
        chosen = bet.get("chosen_option", "")
        if chosen in bet_counts:
            bet_counts[chosen] += 1

    total_bets = sum(bet_counts.values())

    return {
        key: round((bet_counts[key] + 1) / (total_bets + n_opts) * 100, 1)
        for key in option_keys
    }
