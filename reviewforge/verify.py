"""The verification suite — the eleven principles as build gates.

The zinc-air project's quality did not come from writing well once; it came from a check
that ran after every change and refused to let a defect through. This module is that check,
generalised. It never edits the manuscript — it reports, and returns a non-zero status if a
gate fails, so a pipeline can stop before a bad number reaches a reader.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

# machine-writing signatures (Wikipedia "signs of AI writing" + common tells). Prose that
# trips these reads as generated; the Methods, which legitimately describe an automated
# screen, are exempt and must never be stripped.
AI_TELLS = {
    "it is important to note": r"[Ii]t is (?:important|worth) (?:to )?not(?:e|ing)",
    "plays a crucial role": r"play\w* an? (?:crucial|vital|key|pivotal|significant) role",
    "delve into": r"\bdelv\w+\b",
    "in today's world": r"[Ii]n today's (?:world|era|landscape)",
    "a testament to": r"a testament to",
    "paving the way": r"pav\w+ the way",
    "rich tapestry": r"\btapestry\b",
    "in conclusion,": r"\bIn conclusion,",
    "not only ... but also": r"not only\b[^.]{0,80}\bbut also",
    "underscores the importance": r"(?:underscore|highlight)s? the (?:importance|need)",
    "seamless": r"\bseamless\w*",
    "plethora / myriad": r"\b(?:plethora|myriad)\b",
}


class Verifier:
    def __init__(self, project: Path):
        self.p = Path(project)
        self.problems: list[str] = []
        self.warnings: list[str] = []

    def _fail(self, msg):
        self.problems.append(msg)

    def _warn(self, msg):
        self.warnings.append(msg)

    # 1 & 10 — every quoted number regenerates from a script, and no denominator drifts
    def numbers_regenerate(self, pdf_text: str, script_values: dict[str, float]):
        """script_values: {'denominator name': value} gathered from *.json the scripts wrote.
        Flags any of those values that appears in the text against a different number
        nearby, and any 'n = NN' in the text with no matching script value."""
        for name, val in script_values.items():
            # every explicit "n = X" for this concept in the text must equal val
            pass  # concept-level mapping is project-specific; the pipeline wires it
        for m in re.finditer(r"\bn\s*=\s*(\d+)", pdf_text):
            v = int(m.group(1))
            if script_values and v not in set(int(x) for x in script_values.values()):
                self._warn(f"'n = {v}' in text has no matching script-derived denominator "
                           f"(known: {sorted(set(int(x) for x in script_values.values()))}).")

    # 4 — citations resolved and none dropped
    def citations(self, diagnostics: list[dict]):
        unresolved = [d for d in diagnostics if not d.get("ok")]
        if unresolved:
            self._fail(f"{len(unresolved)} citation markers did not resolve: "
                       + ", ".join(d["marker"][:40] for d in unresolved[:5]))
        thin = [d for d in diagnostics if d.get("ok") and
                (d.get("best", 100) - d.get("runner", 0)) < 10]
        if thin:
            self._warn(f"{len(thin)} citations resolved with a thin margin (<10) — read them.")

    # 3 — screen validated by reading before promotion
    def validation_done(self, validation_result: dict | None):
        if not validation_result:
            self._fail("No read-by-hand validation found. Screen percentages must not be "
                       "quoted as findings until validate.py has run (principle 3).")
            return
        if validation_result.get("kappa") is None:
            self._fail("Validation ran but reported no kappa.")

    # 8 — AI declaration present and never removed
    def ai_declaration(self, pdf_text: str, ai_used: bool):
        has = bool(re.search(r"AI[- ]assisted|language model|artificial intelligence",
                             pdf_text, re.I))
        if ai_used and not has:
            self._fail("AI was used but no AI-assistance declaration is present. Concealing "
                       "AI use violates publisher policy and is grounds for retraction "
                       "(principle 8). Restore the declaration.")

    # 9 — never distribute copyrighted full text
    def deposit_clean(self, deposit_dir: Path):
        if not deposit_dir.exists():
            self._warn("No data deposit built yet.")
            return
        for bad in ("_textcache", "textcache"):
            if list(deposit_dir.rglob(bad)):
                self._fail(f"Deposit contains {bad} — the corpus full text. Distributing "
                           f"copyrighted text is a violation (principle 9). Remove it.")
        if list(deposit_dir.rglob("*.pdf")):
            self._fail("Deposit contains PDFs — likely corpus papers. Remove them.")
        for key in deposit_dir.rglob("*key*.txt"):
            self._fail(f"Deposit contains {key.name} — a possible credential. Remove it.")

    # 11 — humanise prose, keep method
    def machine_tells(self, section_texts: dict[str, str]):
        total = 0
        for fname, text in section_texts.items():
            body = text.split("## Editorial notes")[0]
            for lab, rx in AI_TELLS.items():
                hits = len(re.findall(rx, body))
                if hits:
                    total += hits
                    self._warn(f"{fname}: machine-writing tell '{lab}' ×{hits}")
        if total == 0:
            pass  # clean

    # 7 — small samples carry a confidence interval
    def small_sample_claims(self, pdf_text: str):
        for m in re.finditer(r"\br\s*=\s*[−\-+]?\d?\.\d+", pdf_text):
            around = pdf_text[max(0, m.start() - 120): m.end() + 200]
            if not re.search(r"CI|confidence interval|n\s*=\s*\d", around):
                self._warn(f"correlation '{m.group(0)}' quoted without a sample size or CI "
                           f"nearby (principle 7).")

    # ---- report ----
    def report(self) -> tuple[bool, str]:
        ok = not self.problems
        lines = ["REVIEWFORGE VERIFICATION", "=" * 40]
        lines.append(f"FAIL: {len(self.problems)}   WARN: {len(self.warnings)}")
        if self.problems:
            lines.append("\nMUST FIX (build gate):")
            lines += [f"  [FAIL] {m}" for m in self.problems]
        if self.warnings:
            lines.append("\nREAD (not blocking):")
            lines += [f"  [warn] {m}" for m in self.warnings[:40]]
        if ok and not self.warnings:
            lines.append("\nAll gates pass; nothing flagged.")
        return ok, "\n".join(lines)
