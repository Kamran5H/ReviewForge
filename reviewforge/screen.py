"""The reproducible lexical screen — ReviewForge's signature methodology.

Every subset denominator and every "X% of studies report Y" figure a review quotes is
computed here and nowhere else, from a config-defined list of items, and written to
screen.json. The review's tables are rendered from that file, so a number can never drift
away from the code that produced it.

Two hard-won rules from the zinc-air project are baked in:
  1. Every result is a LOWER BOUND on reporting (the screen reads a text layer; anything in
     a figure or in supporting information is scored absent). Percentages are labelled so.
  2. A match that must concern the topic system rather than an adjacent one is confirmed by
     a proximity window: a topic term must sit within N characters and no competing term.
     This is what stopped "in air cathodes" being counted as a cell atmosphere.

The screen's output is never trusted on its own. `validate.py` reads a random sample by
hand and reports the agreement rate before any percentage is promoted to a claim.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path

from .config import Config, ScreenItem, Subset


def _compile(patterns: list[str]) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I)


class Screen:
    def __init__(self, cfg: Config, textcache_dir: Path):
        self.cfg = cfg
        self.cache = Path(textcache_dir)
        self.topic = _compile(cfg.topic_terms) if cfg.topic_terms else None
        self.competing = _compile(cfg.competing_terms) if cfg.competing_terms else None
        self._items = [(it, _compile(it.patterns)) for it in cfg.screen_items]

    # ---- per-paper matching ----
    def _qualified(self, text: str, item: ScreenItem, rx: re.Pattern) -> bool:
        """A match, optionally confirmed to concern the topic system by a window test."""
        for m in rx.finditer(text):
            if item.window <= 0:
                return True
            w = text[max(0, m.start() - item.window): m.end() + item.window]
            ok_ctx = (not item.context_terms) or any(
                re.search(re.escape(t), w, re.I) for t in item.context_terms)
            bad = (item.exclude_terms and any(
                re.search(re.escape(t), w, re.I) for t in item.exclude_terms)) \
                or (self.competing and self.competing.search(w))
            if ok_ctx and not bad:
                return True
        return False

    def _topic_stats(self, text: str) -> tuple[int, int]:
        th = len(self.topic.findall(text)) if self.topic else 0
        ch = len(self.competing.findall(text)) if self.competing else 0
        return th, ch

    def classify(self, fname: str, text: str, title: str) -> dict:
        text = re.sub(r"[ \t]+", " ", text)
        th, ch = self._topic_stats(text)
        rec = {
            "file": fname,
            "title": title,
            "topic_hits": th,
            "competing_hits": ch,
            "topic_dominant": th > 0 and ch <= th * 0.5,
            "head_hits": len(self.topic.findall(text[:20000])) if self.topic else 0,
            "is_review_by_title": bool(re.search(
                r"\breview\b|\bperspective\b|\broadmap\b|\boutlook\b|recent (?:advances|progress)",
                title, re.I)),
        }
        for item, rx in self._items:
            rec[item.key] = self._qualified(text, item, rx)
        return rec

    # ---- subsets ----
    def in_subset(self, rec: dict, s: Subset) -> bool:
        if rec["head_hits"] < s.min_topic_hits and rec["topic_hits"] < s.min_topic_hits:
            return False
        if s.exclude_reviews and rec["is_review_by_title"]:
            return False
        if s.require_full_context and not rec["topic_dominant"]:
            return False
        return True

    # ---- run ----
    def run(self, index: dict, out_path: Path) -> dict:
        recs = []
        for fname, meta in index.items():
            text = (self.cache / meta["cache"]).read_text(encoding="utf-8", errors="replace")
            recs.append(self.classify(fname, text, meta.get("title", fname)))

        report = {"n_corpus": len(recs), "subset_sizes": {}, "rates": {}, "records": recs}
        for s in self.cfg.subsets:
            sub = [r for r in recs if self.in_subset(r, s)]
            report["subset_sizes"][s.name] = len(sub)
            rates = {}
            for item, _ in self._items:
                k = sum(1 for r in sub if r.get(item.key))
                n = len(sub) or 1
                rates[item.key] = {
                    "label": item.label, "n": len(sub), "count": k,
                    "pct": round(100 * k / n, 1),
                    "lower_bound": item.lower_bound,
                }
            report["rates"][s.name] = rates

        Path(out_path).write_text(json.dumps(report, indent=1, ensure_ascii=False),
                                  encoding="utf-8")
        return report

    # ---- a human-readable summary, honest about the lower-bound caveat ----
    @staticmethod
    def summarise(report: dict) -> str:
        lines = [f"Corpus: {report['n_corpus']} records", "", "Subsets:"]
        for name, n in report["subset_sizes"].items():
            lines.append(f"  {name:40s} n = {n}")
        lines.append("")
        lines.append("Every percentage below is a LOWER BOUND on reporting (§Methods), and "
                     "must be validated by reading before it is quoted as a finding.")
        for sname, rates in report["rates"].items():
            lines.append(f"\n[{sname}]")
            for k, v in rates.items():
                flag = " (lower bound)" if v["lower_bound"] else ""
                lines.append(f"  {v['label'][:52]:54s} {v['count']:4d}/{v['n']:<4d} "
                             f"= {v['pct']:5.1f}%{flag}")
        return "\n".join(lines)
