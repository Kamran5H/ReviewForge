"""Length-aware citation resolution — the fix that stopped miscitations.

A review cites papers by a fragment of their title (a marker). Matching that fragment to
the corpus with a naive token-set score produced, in the zinc-air project, one outright
miscitation, one drifting citation and four duplicate pairs — because token_set_ratio
rewards a short marker that is a subset of a long unrelated title. The fix is here:

  * score the marker against both the full title AND the title truncated to the marker's
    own length, and take the harsher of the two — so a marker cannot win by being short;
  * require both a minimum score AND a margin over the runner-up, so an ambiguous marker
    fails loudly instead of resolving to a coin-flip;
  * key the reference list on the RESOLVED record, so two spellings of one title collapse
    to a single entry instead of two.

resolve_markers returns (mapping, order, diagnostics). Diagnostics carry the score, the
runner-up and the reason for every marker, so an audit (verify.py) grades the resolver's
own output rather than re-implementing the matching and grading a different algorithm — the
mistake the first audit script made.
"""
from __future__ import annotations
import re

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None

ACCEPT = 88          # minimum score to accept a match
MARGIN = 6           # required lead over the runner-up


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _score(marker: str, title: str) -> float:
    """Harsher of (marker vs full title) and (marker vs title truncated to marker length).
    Truncation removes the subset-of-a-long-title advantage."""
    if fuzz is None:
        # dependency-free fallback: token overlap ratio
        a, b = set(marker.lower().split()), set(title.lower().split())
        return 100.0 * len(a & b) / max(1, len(a))
    full = fuzz.token_set_ratio(marker, title)
    cut = fuzz.token_set_ratio(marker, title[:len(marker) + 8])
    return min(full, cut)


def resolve_markers(markers: list[str], titles: list[str], manual: dict | None = None):
    """markers in document order -> (mapping{marker:num}, order[list of idx|manual-key],
    diagnostics[list of dicts])."""
    manual = manual or {}
    mapping: dict[str, int] = {}
    order: list = []
    diags: list[dict] = []

    def add(idx_or_key):
        order.append(idx_or_key)
        return len(order)

    for marker in markers:
        marker = _norm(marker)
        if marker in mapping:
            continue

        # manual (non-corpus) references, cited as @key
        m = re.match(r"@(\S+)", marker)
        if m and m.group(1) in manual:
            mapping[marker] = add(m.group(1))
            diags.append({"marker": marker, "num": mapping[marker], "ok": True,
                          "best": 100.0, "runner": 0.0, "reason": "manual"})
            continue

        scored = sorted(((_score(marker, t), i) for i, t in enumerate(titles)), reverse=True)
        best_s, best_i = scored[0]
        runner_s = scored[1][0] if len(scored) > 1 else 0.0

        if best_s >= ACCEPT and (best_s - runner_s) >= MARGIN:
            # collapse onto an already-resolved record if the resolved title matches
            title = titles[best_i]
            existing = next((mk for mk, n in mapping.items()
                             if isinstance(order[n - 1], int) and order[n - 1] == best_i), None)
            mapping[marker] = mapping[existing] if existing else add(best_i)
            diags.append({"marker": marker, "num": mapping[marker], "ok": True,
                          "best": round(best_s, 1), "runner": round(runner_s, 1),
                          "best_title": title, "reason": "resolved"})
        else:
            reason = "below-threshold" if best_s < ACCEPT else "ambiguous (thin margin)"
            diags.append({"marker": marker, "num": None, "ok": False,
                          "best": round(best_s, 1), "runner": round(runner_s, 1),
                          "best_title": titles[best_i], "reason": reason})

    return mapping, order, diags
