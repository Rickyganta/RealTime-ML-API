import math

from scipy.stats import chi2_contingency


def two_proportion_z_test(
    success_a: int, total_a: int, success_b: int, total_b: int
) -> dict[str, float]:
    if total_a == 0 or total_b == 0:
        return {"z_score": 0.0, "p_value": 1.0}

    p1 = success_a / total_a
    p2 = success_b / total_b
    pooled = (success_a + success_b) / (total_a + total_b)
    se = math.sqrt(pooled * (1 - pooled) * ((1 / total_a) + (1 / total_b)))
    if se == 0:
        return {"z_score": 0.0, "p_value": 1.0}

    z = (p1 - p2) / se
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return {"z_score": z, "p_value": p_value}


def chi_square_ctr_summary(
    ctr_counts: dict[str, dict[str, int]],
) -> dict[str, object]:
    strategies = ["collaborative", "content", "hybrid"]
    table = []
    active_strategies: list[str] = []
    for s in strategies:
        clicks = int(ctr_counts.get(s, {}).get("clicks", 0))
        impressions = int(ctr_counts.get(s, {}).get("impressions", 0))
        if impressions == 0:
            continue
        non_clicks = max(impressions - clicks, 0)
        table.append([clicks, non_clicks])
        active_strategies.append(s)

    total_impressions = sum(row[0] + row[1] for row in table)
    if total_impressions == 0 or len(table) < 2:
        return {
            "test": "chi_squared_3x2",
            "p_value": 1.0,
            "statistic": 0.0,
            "dof": 0,
            "active_strategies": active_strategies,
            "pairwise": {},
        }

    try:
        chi2, p_value, dof, _ = chi2_contingency(table)
    except ValueError:
        return {
            "test": "chi_squared_3x2",
            "p_value": 1.0,
            "statistic": 0.0,
            "dof": 0,
            "active_strategies": active_strategies,
            "pairwise": {},
        }

    def _pair(a: str, b: str) -> dict[str, float]:
        a_clicks = int(ctr_counts.get(a, {}).get("clicks", 0))
        a_impr = int(ctr_counts.get(a, {}).get("impressions", 0))
        b_clicks = int(ctr_counts.get(b, {}).get("clicks", 0))
        b_impr = int(ctr_counts.get(b, {}).get("impressions", 0))
        return two_proportion_z_test(a_clicks, a_impr, b_clicks, b_impr)

    pairwise = {
        "collaborative_vs_content": _pair("collaborative", "content"),
        "collaborative_vs_hybrid": _pair("collaborative", "hybrid"),
        "content_vs_hybrid": _pair("content", "hybrid"),
    }

    return {
        "test": "chi_squared_3x2",
        "p_value": float(p_value),
        "statistic": float(chi2),
        "dof": int(dof),
        "active_strategies": active_strategies,
        "pairwise": pairwise,
    }
