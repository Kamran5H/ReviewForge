"""PDF -> normalised text cache. Every screen reads from here, never from the PDFs, so a
change to the corpus is a change to one directory and the classification is reproducible.
"""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path


def build(corpus_dir: Path, cache_dir: Path) -> int:
    corpus_dir, cache_dir = Path(corpus_dir), Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        import fitz
    except ImportError:
        raise SystemExit("pymupdf is required: pip install pymupdf")
    index = {}
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        try:
            d = fitz.open(pdf)
            text = "\n".join(p.get_text() for p in d)
            title = (d.metadata or {}).get("title") or pdf.stem
            d.close()
        except Exception:
            continue
        text = re.sub(r"[ \t]+", " ", text)
        h = hashlib.md5(pdf.name.encode()).hexdigest()[:16] + ".txt"
        (cache_dir / h).write_text(text, encoding="utf-8")
        index[pdf.name] = {"cache": h, "title": title}
    (cache_dir / "_index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    return len(index)
