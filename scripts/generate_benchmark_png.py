from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    out_dir = Path("docs/benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "locust-1000rps.png"

    # Numbers from a long local Locust run (read-heavy, cached GET /recommendations/*, Safari UI export).
    rows = [
        ("Aggregated", 1_342_878, 0, 10, 54, 87, 15.68, 1, 744, 1701.56, 1000.2, 0),
        ("GET /recommendations/101", 1_338_298, 0, 10, 54, 87, 15.64, 1, 744, 1702, 1000.2, 0),
    ]

    cols = [
        "Name",
        "# Requests",
        "# Fails",
        "Median (ms)",
        "95%ile (ms)",
        "99%ile (ms)",
        "Average (ms)",
        "Min (ms)",
        "Max (ms)",
        "Avg size (B)",
        "Current RPS",
        "Failures/s",
    ]

    fig_w = 18
    fig_h = 4.2
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=cols,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.05, 1.25)

    ax.set_title(
        "Locust — local read-heavy load test (cached GET /recommendations/{user_id})",
        fontsize=12,
        pad=12,
    )

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
