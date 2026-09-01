"""Read-by-hand validation of the screen — the step that separates a real review from a
plausible one, and the one thing the framework refuses to fake.

A lexical screen counts strings; it cannot tell the topic system's atmosphere from a furnace
step, or a primary study from a review that mentions one. So before any screen percentage is
promoted from "the screen finds X%" to "we find X%", a random sample is READ — by a human, or
by a language model given the full text and asked to judge — and the two classifications are
compared. This module:

  * draws a reproducible random sample (seeded, in two stages so it can be extended);
  * dumps, for each paper, the passages the screen matched on, so the reader adjudicates the
    evidence rather than trusting the verdict;
  * scores raw agreement, Cohen's kappa, and the confusion matrix, and lists every
    disagreement with its cause — which is what makes the error characterisable in Methods.

The reader verdicts are recorded as data (verdicts.json) so the agreement rate is
recomputable and auditable, exactly as in the zinc-air §9.7.
"""
from __future__ import annotations
import json
import math
import random
import re
from pathlib import Path


def draw_sample(records: list[dict], subset_pred, n: int, seed: int) -> list[dict]:
    """A reproducible random sample of a subset, in two stages so it can be grown later
    without breaking the seed."""
    pool = sorted([r for r in records if subset_pred(r)], key=lambda r: r["file"])
    half = max(1, n // 2)
    first = sorted(random.Random(seed).sample(pool, min(half, len(pool))),
                   key=lambda r: r["file"])
    rest = [r for r in pool if r not in first]
    second = sorted(random.Random(seed + 1).sample(rest, min(n - len(first), len(rest))),
                    key=lambda r: r["file"])
    return first + second


def dump_for_reading(sample: list[dict], cache: Path, index: dict, item_key: str,
                     patterns: list[str], out_path: Path) -> None:
    """Write, for each sampled paper, the automated verdict and the passages that produced
    it, so a reader can decide. Reference-list matches are flagged: they are the classic
    false positive."""
    rx = re.compile("|".join(patterns), re.I)
    reflist = re.compile(r"\bReferences\b|\bBibliography\b")
    blocks = []
    for i, r in enumerate(sample, 1):
        t = re.sub(r"[ \t]+", " ", (cache / index[r["file"]]["cache"])
                   .read_text(encoding="utf-8", errors="replace"))
        cut = [m.start() for m in reflist.finditer(t)]
        body_end = cut[-1] if cut and cut[-1] > len(t) * 0.5 else len(t)
        ev = []
        for m in list(rx.finditer(t))[:4]:
            where = "BODY" if m.start() < body_end else "REFLIST(likely false positive)"
            ev.append(f"  <{where}> …{t[max(0, m.start()-180):m.end()+180]}…")
        blocks.append(f"[{i}/{len(sample)}] auto={r.get(item_key)}  {r['title'][:90]}\n" +
                      ("\n".join(ev) if ev else "  (no passage matched)"))
    Path(out_path).write_text("\n\n".join(blocks), encoding="utf-8")


def score(reader_verdicts: list[dict], auto_key: str) -> dict:
    """reader_verdicts: [{file, auto: bool/str, reader: 'yes'|'no'|'not_applicable', note}].
    Returns agreement, kappa, confusion matrix, and the characterised disagreements."""
    real = [r for r in reader_verdicts if r["reader"] != "not_applicable"]
    not_applicable = [r for r in reader_verdicts if r["reader"] == "not_applicable"]

    def a(r):
        return "yes" if r["auto"] in (True, "yes") else "no"

    cats = ("yes", "no")
    M = {x: {y: 0 for y in cats} for x in cats}
    for r in real:
        M[a(r)][r["reader"]] += 1
    n = len(real) or 1
    agree = sum(M[c][c] for c in cats)
    po = agree / n
    pe = sum((sum(M[x].values()) / n) * (sum(M[y][x] for y in cats) / n) for x in cats)
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 0.0

    fp = [r for r in real if a(r) == "yes" and r["reader"] == "no"]
    fn = [r for r in real if a(r) == "no" and r["reader"] == "yes"]

    def wilson(k, m, z=1.96):
        if m == 0:
            return (0.0, 0.0)
        q = k / m; d = 1 + z * z / m
        c = (q + z * z / (2 * m)) / d
        h = z * math.sqrt(q * (1 - q) / m + z * z / (4 * m * m)) / d
        return round(100 * (c - h), 1), round(100 * (c + h), 1)

    reader_yes = sum(1 for r in real if r["reader"] == "yes")
    return {
        "n_sample": len(reader_verdicts),
        "not_applicable": len(not_applicable),
        "n_real": len(real),
        "raw_agreement": agree,
        "agreement_pct": round(100 * po, 1),
        "kappa": round(kappa, 3),
        "matrix": M,
        "false_positives": fp,
        "false_negatives": fn,
        "reader_finding_pct": round(100 * reader_yes / n, 1),
        "reader_finding_ci": wilson(reader_yes, len(real)),
        "note": "The reader_finding figure, not the screen's, is what the review should "
                "quote. If they differ, the screen is a lower bound and this is why.",
    }
