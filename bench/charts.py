"""Builds the charts from results/summary.json.

Outputs:
    results/before_after.png   chart used in the README
    results/RESULTS.md         results table, ready to paste into the README
    docs/cover.png             1600x1200 cover image for a portfolio card (Upwork, Workana, LinkedIn)

Every number in the images is read from summary.json. Nothing is typed by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BEFORE, AFTER = "#B4413C", "#1F6F8B"
INK, MUTED, GRID, BG, CARD = "#1C2430", "#5B6676", "#E3E7EC", "#F6F8FA", "#FFFFFF"

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": INK})


def fmt_ms(ms: float) -> str:
    if ms < 1:
        return f"{ms:.2f} ms"
    if ms < 1000:
        return f"{ms:.0f} ms" if ms >= 10 else f"{ms:.1f} ms"
    s = ms / 1000
    if s < 60:
        return f"{s:.1f} s"
    m, s = divmod(round(s), 60)
    return f"{m} min {s:02d} s"


def fmt_num(n: float) -> str:
    return f"{n:,.0f}"


def speedup(before: float, after: float) -> str:
    x = before / after if after else float("inf")
    return f"{x:,.0f}x faster" if x >= 10 else f"{x:.1f}x faster"


def short_db(summary: dict) -> str:
    """'Oracle Database 23ai Free Release 23.0.0.0.0 - Develop, ...' -> text before the first ' - '."""
    return summary["database"].splitlines()[0].split(" - ")[0].strip()


def load() -> dict:
    path = ROOT / "results" / "summary.json"
    if not path.exists():
        sys.exit("results/summary.json not found. Run bench/bench.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def readme_chart(summary: dict) -> Path:
    cases = list(summary["cases"].values())
    fig, axes = plt.subplots(len(cases), 1, figsize=(10, 1.9 * len(cases) + 0.6))
    if len(cases) == 1:
        axes = [axes]
    for ax, case in zip(axes, cases):
        b, a = case["before"]["elapsed_ms"], case["after"]["elapsed_ms"]
        ax.barh([1, 0], [b, a], color=[BEFORE, AFTER], height=0.6)
        ax.set_yticks([1, 0], ["Before", "After"])
        ax.set_xlim(0, max(a, b) * 1.22)
        for y, v in ((1, b), (0, a)):
            ax.text(v + max(a, b) * 0.015, y, fmt_ms(v), va="center", fontsize=11, color=INK)
        title = f"{case['title']}  ({case['unit']})"
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
        ax.text(1.0, 1.02, speedup(b, a), transform=ax.transAxes, ha="right", va="bottom",
                fontsize=11, fontweight="bold", color=AFTER)
        ax.tick_params(axis="x", which="both", labelbottom=False, length=0)
        for side in ("top", "right", "bottom"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color(GRID)
    fig.text(0.01, 0.005, "Elapsed time (linear scale). Median of repeated runs, warm cache. "
             f"{short_db(summary)}", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = ROOT / "results" / "before_after.png"
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)
    return out


def cover(summary: dict) -> Path:
    fig = plt.figure(figsize=(16, 12), dpi=100, facecolor=BG)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis("off")

    ax.text(1, 10.75, "Oracle SQL Performance Tuning", fontsize=44, fontweight="bold", color=INK)
    ax.text(1, 10.0, "Three common production problems, fixed and measured before and after",
            fontsize=21, color=MUTED)

    cases = list(summary["cases"].values())
    top, height, gap = 8.9, 2.45, 0.35
    for i, case in enumerate(cases):
        y = top - i * (height + gap) - height
        ax.add_patch(FancyBboxPatch((1, y), 14, height, boxstyle="round,pad=0,rounding_size=0.25",
                                    facecolor=CARD, edgecolor=GRID, linewidth=1.5))
        b, a = case["before"]["elapsed_ms"], case["after"]["elapsed_ms"]
        ax.text(1.5, y + height - 0.65, case["title"], fontsize=24, fontweight="bold", color=INK)
        ax.text(1.5, y + height - 1.25, case["unit"].capitalize(), fontsize=16, color=MUTED)
        ax.text(1.5, y + 0.55, fmt_ms(b), fontsize=30, fontweight="bold", color=BEFORE)
        ax.text(5.6, y + 0.55, "→", fontsize=30, color=MUTED)
        ax.text(6.6, y + 0.55, fmt_ms(a), fontsize=30, fontweight="bold", color=AFTER)
        ax.text(14.5, y + height - 0.9, speedup(b, a), fontsize=28, fontweight="bold", color=AFTER, ha="right")
        extra = ""
        lb, la = case["before"].get("logical_reads"), case["after"].get("logical_reads")
        if lb and la:
            extra = f"Logical reads: {fmt_num(lb)} → {fmt_num(la)}"
        dbl = case.get("double_submission")
        if dbl:
            extra = (f"Duplicate prices on retry: {fmt_num(dbl['before']['duplicate_keys'])} "
                     f"→ {fmt_num(dbl['after']['duplicate_keys'])}")
        if extra:
            ax.text(14.5, y + 0.6, extra, fontsize=16, color=MUTED, ha="right")

    db = short_db(summary)
    ax.text(1, 0.55, f"Identical results before and after  ·  {db}  ·  synthetic data, "
            f"{fmt_num(summary['data']['n_orders'])} orders", fontsize=14, color=MUTED)
    out = ROOT / "docs" / "cover.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=100, facecolor=BG)
    plt.close(fig)
    return out


def results_table(summary: dict) -> Path:
    lines = ["| Case | Before | After | Speed-up | Logical reads (before -> after) | Same result |",
             "|---|---:|---:|---:|---:|:---:|"]
    for case in summary["cases"].values():
        b, a = case["before"], case["after"]
        lr = (f"{fmt_num(b['logical_reads'])} -> {fmt_num(a['logical_reads'])}"
              if b.get("logical_reads") and a.get("logical_reads") else "n/a")
        lines.append(f"| {case['title']} ({case['unit']}) | {fmt_ms(b['elapsed_ms'])} | {fmt_ms(a['elapsed_ms'])} "
                     f"| {speedup(b['elapsed_ms'], a['elapsed_ms']).replace(' faster', '')} | {lr} "
                     f"| {'yes' if case.get('identical_results') else 'NO'} |")
    dbl = summary["cases"].get("case3", {}).get("double_submission")
    if dbl:
        lines += ["", "Double submission test (two sessions load the same file at the same time):", "",
                  "| Version | Duplicate product/date keys | Rows in price list |", "|---|---:|---:|",
                  f"| Before | {fmt_num(dbl['before']['duplicate_keys'])} | {fmt_num(dbl['before']['rows'])} |",
                  f"| After | {fmt_num(dbl['after']['duplicate_keys'])} | {fmt_num(dbl['after']['rows'])} |"]
    lines += ["", f"Environment: {short_db(summary)}; {summary['client']}; {summary['machine']}.",
              f"Data: {fmt_num(summary['data']['n_customers'])} customers, {fmt_num(summary['data']['n_orders'])} orders, "
              f"{fmt_num(summary['data']['n_skus'] * 4)} prices, {fmt_num(summary['data']['n_stg'])}-line upload file.",
              f"Method: {summary['method']}. Generated {summary['generated_at']}."]
    out = ROOT / "results" / "RESULTS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    data = load()
    print("Wrote", results_table(data).relative_to(ROOT))
    print("Wrote", readme_chart(data).relative_to(ROOT))
    print("Wrote", cover(data).relative_to(ROOT))
