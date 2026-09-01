"""Multi-API open-access literature retrieval, relevance-gated. Generalised from the
zinc-air harvester: one query, several free scholarly APIs, a title-level relevance gate so
adjacent fields do not leak in, and a record of exactly what was run (written to the corpus
directory) for the Methods section.

This module fetches METADATA and open-access PDF links. Downloading PDFs is left to the
user's existing tooling or a manual step, because bulk downloading touches copyright and
rate-limits that are the author's responsibility, not the framework's.
"""
from __future__ import annotations
import json, re, time, urllib.parse, urllib.request
from pathlib import Path
from .config import Config


def _get(url, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(url + "?" + q, headers={"User-Agent": "ReviewForge/1.0 (mailto:researcher@example.org)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _relevant(title, terms):
    t = re.sub(r"\W+", " ", (title or "").lower())
    hits = sum(1 for term in terms if term.lower() in t)
    return hits >= max(1, len(terms) // 3)


def _openalex(cfg, need):
    out, cursor = [], "*"
    while len(out) < need:
        d = _get("https://api.openalex.org/works", {
            "filter": f"title_and_abstract.search:{cfg.query},open_access.is_oa:true,"
                      f"from_publication_date:{cfg.year_start}-01-01,"
                      f"to_publication_date:{cfg.year_end}-12-31",
            "per-page": 200, "cursor": cursor,
            "select": "title,doi,publication_year,authorships,primary_location",
            "mailto": "researcher@example.org"})
        if not d or not d.get("results"):
            break
        for it in d["results"]:
            title = it.get("title") or ""
            if _relevant(title, cfg.topic_terms):
                out.append({"title": title, "doi": (it.get("doi") or "").replace("https://doi.org/", ""),
                            "year": it.get("publication_year"), "source": "openalex"})
        cursor = d.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.3)
    return out


def run(cfg: Config, corpus_dir: Path) -> int:
    corpus_dir = Path(corpus_dir); corpus_dir.mkdir(parents=True, exist_ok=True)
    records, seen = [], set()
    # OpenAlex is the workhorse; other APIs plug in the same way (kept minimal here).
    for rec in _openalex(cfg, cfg.max_papers):
        key = rec["doi"] or rec["title"][:60].lower()
        if key not in seen:
            seen.add(key); records.append(rec)
        if len(records) >= cfg.max_papers:
            break
    (corpus_dir / "harvest_records.json").write_text(
        json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")
    # the provenance the Methods section needs
    (corpus_dir / "harvest_provenance.txt").write_text(
        f"query: {cfg.query!r}\napis: {cfg.apis}\nyears: {cfg.year_start}-{cfg.year_end}\n"
        f"relevance gate: >= {max(1, len(cfg.topic_terms)//3)} of {cfg.topic_terms}\n"
        f"retrieved: {len(records)} records\n"
        f"NOTE: this fetched metadata + OA links. Download PDFs into corpus/ separately.\n",
        encoding="utf-8")
    return len(records)
