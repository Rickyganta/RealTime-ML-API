"""Render a wide PNG for README header (Streamlit-style layout; run `make dashboard` for the live app)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Approximate Streamlit light theme
BG = "#ffffff"
TEXT = "#31333F"
MUTED = "#6c757d"
def main() -> None:
    out = Path("docs/images/streamlit-dashboard.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(14, 5.5), dpi=160, facecolor=BG)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor(BG)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    # Title row (matches dashboard/app.py)
    ax.text(
        0.35,
        4.85,
        "Movie recs — local admin",
        fontsize=22,
        fontweight="600",
        color=TEXT,
        ha="left",
        va="top",
    )
    ax.text(
        0.35,
        4.45,
        "Main   ·   Performance (Locust)",
        fontsize=11,
        color=MUTED,
        ha="left",
        va="top",
    )

    # KPI cards
    cards = [
        ("Average Latency", "2.30 ms"),
        ("Cache Hit Rate", "100.0%"),
        ("Total Interactions", "0"),
    ]
    x0, w_card, gap = 0.35, 3.9, 0.45
    y_card = 2.15
    h_card = 1.55
    for i, (label, value) in enumerate(cards):
        x = x0 + i * (w_card + gap)
        rect = mpatches.FancyBboxPatch(
            (x, y_card),
            w_card,
            h_card,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1,
            edgecolor="#e6e9ef",
            facecolor="#fafafa",
        )
        ax.add_patch(rect)
        ax.text(
            x + 0.2,
            y_card + h_card - 0.35,
            label,
            fontsize=11,
            color=MUTED,
            ha="left",
            va="top",
        )
        ax.text(
            x + 0.2,
            y_card + 0.55,
            value,
            fontsize=20,
            fontweight="600",
            color=TEXT,
            ha="left",
            va="bottom",
        )

    ax.text(
        0.35,
        1.55,
        "CTR by strategy (A/B bucket)",
        fontsize=14,
        fontweight="600",
        color=TEXT,
        ha="left",
        va="top",
    )

    # Bar chart (illustrative CTRs; live app uses /admin/ab/results)
    strat = ["collaborative", "content", "hybrid"]
    vals = [0.08, 0.06, 0.11]
    colors = ["#4c78a8", "#f58518", "#54a24b"]
    base_y, max_h, bw, gap_b = 0.22, 0.55, 0.85, 0.55
    bx0 = 1.2
    vmax = max(vals)
    for i, (name, v, c) in enumerate(zip(strat, vals, colors)):
        x = bx0 + i * (bw + gap_b)
        h = (v / vmax) * max_h if vmax else 0
        rect = mpatches.Rectangle((x, base_y), bw, h, facecolor=c, edgecolor="none", alpha=0.9)
        ax.add_patch(rect)
        cx = x + bw / 2
        ax.text(cx, base_y + h + 0.06, f"{v:.2f}", ha="center", va="bottom", fontsize=10, color=TEXT)
        ax.text(cx, base_y - 0.06, name, ha="center", va="top", fontsize=9, color=MUTED)

    fig.savefig(out, bbox_inches="tight", pad_inches=0.15, facecolor=BG)
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
