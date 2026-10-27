"""README chart: recall@10 at each step of the retrieval pipeline, read from eval/results/<split>.json.

  uv run --with matplotlib python -m eval.chart --split test   ->  docs/recall-light.png, docs/recall-dark.png
"""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from eval.run import HERE, summarize  # noqa: E402

STEPS = [  # (results key, label) in pipeline order; the last one is shipped
    ("fixed512|dense", "Fixed 512-token chunks, dense"),
    ("section512|dense", "One chunk per section, dense"),
    ("section512|hybrid", "+ sparse, fused by RRF (hybrid)"),
    ("section512|routed", "Dense, routed by jurisdiction"),
    ("section512|routed_rerank", "Routed + reranked (shipped)"),
]
# One blue ordinal ramp per surface, checked with the dataviz palette validator (--ordinal) against that surface.
THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#6f6e69", "grid": "#e1e0d9",
              "base": "#c3c2b7", "bar": "#86b6ef", "shipped": "#2a78d6"},
    "dark": {"surface": "#0d1117", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#9a9891", "grid": "#262a30",
             "base": "#3d4148", "bar": "#1c5cab", "shipped": "#5598e7"},
}


def draw(values: list[float], n: int, split: str, theme: str, out) -> None:
    t = THEMES[theme]
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10})
    fig, ax = plt.subplots(figsize=(8, 3.5), dpi=200)
    fig.subplots_adjust(left=0.31, right=0.95, top=0.76, bottom=0.12)
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(STEPS) - 0.4)
    for side in ax.spines.values():
        side.set_visible(False)

    box = ax.get_window_extent()  # pixels, so the rounded bar ends come out round, not elliptical
    x_per_px, y_per_px = 100 / box.width, len(STEPS) / box.height
    radius = 8 * x_per_px  # 4px at the README's ~2x downscale
    height = 44 * y_per_px  # <= 24px thick when displayed
    ax.vlines([25, 50, 75, 100], -0.6, len(STEPS) - 0.4, color=t["grid"], lw=1, zorder=0)
    ax.axvline(0, color=t["base"], lw=1, zorder=3)

    for i, ((_, label), v) in enumerate(zip(STEPS, values)):
        y = len(STEPS) - 1 - i  # first step on top
        shipped = i == len(STEPS) - 1
        color = t["shipped"] if shipped else t["bar"]
        ax.add_patch(FancyBboxPatch((0, y - height / 2), v, height, mutation_aspect=y_per_px / x_per_px,
                                    boxstyle=f"round,pad=0,rounding_size={radius}", lw=0, color=color, zorder=2))
        ax.add_patch(Rectangle((0, y - height / 2), min(2 * radius, v), height, lw=0, color=color, zorder=2))
        ax.text(v + 1.4, y, f"{v:.1f}%", va="center", ha="left", fontsize=10.5,
                color=t["ink"] if shipped else t["ink2"], fontweight="semibold" if shipped else "normal")

    ax.set_yticks(range(len(STEPS) - 1, -1, -1), [label for _, label in STEPS])
    for tick, (_, label) in zip(ax.get_yticklabels(), STEPS):
        shipped = label == STEPS[-1][1]
        tick.set_color(t["ink"] if shipped else t["ink2"])
        tick.set_fontweight("semibold" if shipped else "normal")
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], color=t["muted"], fontsize=9)
    ax.tick_params(length=0, pad=8)

    fig.text(0.02, 0.93, f"Recall@10 on the {split} questions", fontsize=13, fontweight="semibold", color=t["ink"])
    fig.text(0.02, 0.855, f"Share of the gold legal sections retrieved in the top 10 · {n} answerable questions",
             fontsize=9.5, color=t["ink2"])
    fig.savefig(out, facecolor=t["surface"])
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="test", choices=["dev", "test", "all"])
    split = p.parse_args().split
    runs = json.loads((HERE / "results" / f"{split}.json").read_text(encoding="utf-8"))["retrieval"]
    stats = [summarize(runs[key]) for key, _ in STEPS]
    docs = HERE.parent / "docs"
    docs.mkdir(exist_ok=True)
    for theme in THEMES:
        draw([s["recall@10"] for s in stats], stats[-1]["n"], split, theme, docs / f"recall-{theme}.png")
    print("wrote", ", ".join(f"docs/recall-{theme}.png" for theme in THEMES))


if __name__ == "__main__":
    main()
