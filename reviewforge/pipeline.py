"""The orchestrator — the loop that ran hundreds of times, as one object.

Stages are independent and each writes an audit file; nothing downstream trusts an
unverified upstream number. A stage can be re-run without re-running the others. The order
mirrors the zinc-air project: harvest → cache → screen → validate (READ HERE) → draft
(LLM) → figures → compile → verify.
"""
from __future__ import annotations
import json
from pathlib import Path

from .config import Config
from .screen import Screen
from .verify import Verifier


class Pipeline:
    STAGES = ["harvest", "cache", "screen", "validate", "draft",
              "figures", "compile", "verify"]

    def __init__(self, project_dir: str | Path):
        self.dir = Path(project_dir)
        self.cfg = Config.load(self.dir / "config.yaml")
        self.cfg.project_dir = str(self.dir)
        for sub in ("corpus", "textcache", "analysis", "sections", "figures", "output"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    # ---- individual stages (thin wrappers; heavy logic lives in the modules) ----
    def harvest(self):
        from . import harvest
        n = harvest.run(self.cfg, self.dir / "corpus")
        return f"harvested {n} records"

    def cache(self):
        from . import textcache
        n = textcache.build(self.dir / "corpus", self.dir / "textcache")
        return f"cached text for {n} papers"

    def screen(self):
        index = json.loads((self.dir / "textcache" / "_index.json").read_text(encoding="utf-8"))
        s = Screen(self.cfg, self.dir / "textcache")
        report = s.run(index, self.dir / "analysis" / "screen.json")
        (self.dir / "analysis" / "screen_summary.txt").write_text(
            Screen.summarise(report), encoding="utf-8")
        return Screen.summarise(report)

    def validate(self):
        return ("Validation is a READING step. Run:\n"
                "  python -m reviewforge sample <project>   # dumps the sample to read\n"
                "then record verdicts in analysis/verdicts.json and run:\n"
                "  python -m reviewforge score <project>    # computes agreement + kappa\n"
                "No screen percentage becomes a claim until this is done.")

    def draft(self):
        return ("Drafting is an LLM step (stages.draft_section). It needs a backend in "
                "config.yaml. Each section is drafted from its evidence and written to "
                "sections/; then edited by you. The framework does not auto-accept a draft.")

    def figures(self):
        from . import figures
        n = figures.build(self.cfg, self.dir / "analysis", self.dir / "figures")
        return f"generated {n} original figures"

    def compile(self):
        from . import compile as comp
        out = comp.build(self.cfg, self.dir)
        return f"compiled {out}"

    def verify(self):
        v = Verifier(self.dir)
        # wire whatever exists; missing inputs become their own flags
        an = self.dir / "analysis"
        screen = json.loads((an / "screen.json").read_text(encoding="utf-8")) \
            if (an / "screen.json").exists() else {}
        diags = json.loads((an / "resolve_diag.json").read_text(encoding="utf-8")) \
            if (an / "resolve_diag.json").exists() else []
        valres = json.loads((an / "validation.json").read_text(encoding="utf-8")) \
            if (an / "validation.json").exists() else None
        secs = {p.name: p.read_text(encoding="utf-8")
                for p in (self.dir / "sections").glob("*.md")}
        pdf_txt = ""
        pdf = self.dir / "output" / "review.pdf"
        if pdf.exists():
            try:
                import fitz
                pdf_txt = "\n".join(pg.get_text() for pg in fitz.open(pdf))
            except Exception:
                pass
        v.citations(diags)
        v.validation_done(valres)
        v.machine_tells(secs)
        if pdf_txt:
            v.ai_declaration(pdf_txt, ai_used=self.cfg.llm.backend != "none")
            v.small_sample_claims(pdf_txt)
            denoms = {k: s["n"] for r in screen.get("rates", {}).values() for k, s in r.items()}
            v.numbers_regenerate(pdf_txt, denoms)
        v.deposit_clean(self.dir / "output" / "deposit")
        ok, text = v.report()
        (self.dir / "output" / "VERIFICATION.txt").write_text(text, encoding="utf-8")
        return text

    def run(self, stage: str) -> str:
        if stage not in self.STAGES:
            raise ValueError(f"unknown stage {stage!r}; choose from {self.STAGES}")
        return getattr(self, stage)()
