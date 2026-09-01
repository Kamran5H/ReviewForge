"""Original figures from the corpus screen — the review's own analysis, not reproduced
panels. Generalised from the zinc-air own-figures: a reporting-rate bar chart and a
screening funnel, both driven entirely by screen.json, at print resolution.

These carry no reproduction credit because they are the authors' own. Add topic-specific
figures (scatter of two reported quantities, etc.) as further functions.
"""
from __future__ import annotations
import json
from pathlib import Path


def build(cfg, analysis_dir: Path, fig_dir: Path) -> int:
    analysis_dir, fig_dir = Path(analysis_dir), Path(fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    screen_path = analysis_dir / "screen.json"
    if not screen_path.exists():
        return 0
    rep = json.loads(screen_path.read_text(encoding="utf-8"))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return 0
    NAVY, RED = "#1A3A5C", "#B03A2E"
    plt.rcParams.update({"font.size": 9, "figure.dpi": 600, "savefig.bbox": "tight"})
    made = 0

    # 1) reporting-rate bars for the primary subset (whichever excludes reviews, else first)
    sname = next((s.name for s in cfg.subsets if s.exclude_reviews),
                 (cfg.subsets[0].name if cfg.subsets else None))
    if sname and sname in rep.get("rates", {}):
        rates = rep["rates"][sname]
        items = sorted(rates.values(), key=lambda v: v["pct"])
        fig, ax = plt.subplots(figsize=(6.3, 0.5 * len(items) + 1))
        ys = range(len(items))
        ax.barh(list(ys), [v["pct"] for v in items], color=NAVY, height=0.6)
        for y, v in zip(ys, items):
            ax.text(v["pct"] + 1, y, f'{v["pct"]:.0f}%', va="center", fontsize=8, color=NAVY)
        ax.set_yticks(list(ys)); ax.set_yticklabels([v["label"][:46] for v in items], fontsize=7.5)
        ax.set_xlim(0, 100); ax.set_xlabel(f"Share of the {sname} (n = {items[0]['n']}), a lower bound")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        fig.savefig(fig_dir / "own_reporting_rates.png"); plt.close(fig); made += 1

    # 2) screening funnel across the configured subsets
    sizes = rep.get("subset_sizes", {})
    if sizes:
        fig, ax = plt.subplots(figsize=(6.3, 0.6 * len(sizes) + 1))
        names = list(sizes.keys()); vals = [sizes[n] for n in names]
        ys = range(len(names))[::-1]
        for y, (n, v) in zip(ys, zip(names, vals)):
            col = RED if v == 0 else NAVY
            ax.barh(y, max(v, 1), color=col, height=0.6)
            ax.text(max(v, 1) + max(vals) * 0.01, y, "none" if v == 0 else str(v),
                    va="center", fontsize=8.5, color=col, fontweight="bold")
        ax.set_yticks(list(ys)); ax.set_yticklabels(names[::-1], fontsize=8)
        ax.set_xlabel("Number of studies")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        fig.savefig(fig_dir / "own_funnel.png"); plt.close(fig); made += 1
    return made
