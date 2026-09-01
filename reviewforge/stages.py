"""The judgement stages — where the review stops being mechanical.

Each function here delegates a reasoning task to the LLM, with a prompt that encodes what
the zinc-air project learned about doing it well. These are the steps a static script cannot
do: they require reading, weighing, and being willing to conclude that the paper's own claim
is wrong. The prompts are deliberately adversarial and evidence-bound, because that is what
produced a defensible review rather than a plausible one.

Nothing here is trusted blindly. Every output is written to disk for a human to read, and
the claims it produces feed back through screen.py and validate.py to be checked against the
corpus. The LLM proposes; the deterministic tools and the author dispose.
"""
from __future__ import annotations
import json
from pathlib import Path

from .llm import LLM


def hunt_thesis(llm: LLM, topic: str, screen_summary: str, section_intents: list[str]) -> str:
    """Ask for a NOVEL, FALSIFIABLE central claim — and warn against the tidy version.

    The zinc-air thesis was found this way, and its first form was wrong (a symmetric
    'all three conditions are antagonistic' that the corpus refuted). The prompt therefore
    demands a claim that could be false, and asks explicitly which part is weakest."""
    system = (
        "You are a senior reviewer looking for the ONE claim that makes a review worth "
        "publishing. It must be novel (not already the field's consensus), falsifiable "
        "(a single counterexample would refute it), and mechanistic (a cause, not a "
        "complaint). Distrust tidy, symmetric claims — reality is rarely symmetric, and a "
        "reviewer punishes a structure that is too neat. State the claim in two sentences, "
        "then name the single weakest link in it and the one experiment or corpus query "
        "that would test it.")
    user = (f"Topic: {topic}\n\nWhat the corpus screen found (lower bounds):\n{screen_summary}"
            f"\n\nWhat each section can establish:\n" + "\n".join(f"- {s}" for s in section_intents)
            + "\n\nPropose the central thesis.")
    return llm.complete(system, user)


def adversarial_review(llm: LLM, thesis: str, screen_summary: str) -> str:
    """Attack the paper's own thesis against the corpus. This is principle 6. In the
    zinc-air project this step killed one third of the thesis and made the rest stronger."""
    system = (
        "You are a hostile referee. Your job is to REFUTE the thesis below using the "
        "evidence given, not to improve it. For each component of the claim: is it "
        "supported, unsupported, or contradicted by the corpus? Quantify where you can. If "
        "any part fails, say so plainly and state what the corrected claim should be. Do not "
        "be polite; a thesis that survives you is worth keeping.")
    user = f"THESIS:\n{thesis}\n\nCORPUS EVIDENCE (lower bounds):\n{screen_summary}"
    return llm.complete(system, user)


def classify_by_reading(llm: LLM, question: str, paper_text: str) -> dict:
    """Classify one paper by reading it — the validation step. Returns a verdict and the
    sentence that decided it, so a human can adjudicate. The LLM is told to distrust matches
    in the reference list and in synthesis/characterisation passages, which were the classic
    false positives."""
    system = (
        "You classify a paper by reading it, not by keyword. Answer only from what the paper "
        "states about ITS OWN cell/system. Ignore: the reference list; synthesis, "
        "calcination, drying or thermogravimetric steps; generic introductory sentences; and "
        "descriptions of other groups' work. Reply as JSON: "
        '{"verdict": "yes"|"no"|"not_applicable", "evidence": "the exact deciding sentence", '
        '"reason": "why"}. "not_applicable" means the paper has no system of its own (a '
        "review, a roadmap, a different subject).")
    user = f"QUESTION: {question}\n\nPAPER TEXT (truncated):\n{paper_text[:12000]}"
    out = llm.complete(system, user)
    try:
        return json.loads(out[out.index("{"): out.rindex("}") + 1])
    except Exception:
        return {"verdict": "not_applicable", "evidence": "", "reason": "unparseable: " + out[:200]}


def draft_section(llm: LLM, section_title: str, intent: str, evidence: str,
                  style_notes: str = "") -> str:
    """Draft one section from the evidence gathered for it. The prompt forbids the machine
    tells that verify.py scans for, and requires every quantitative claim to name its
    source — so the draft arrives already close to the standard the verifier enforces."""
    system = (
        "You write critical scientific prose for a high-impact review. Rules: lead with the "
        "claim, not the throat-clearing. No 'it is important to note', no 'plays a crucial "
        "role', no 'delve', no rule-of-three padding, no em-dash overuse. Vary sentence "
        "length. Every number must name where it comes from (a table, a screen, a citation). "
        "Never assert a value you were not given. Prefer the honest weaker claim over the "
        "impressive unsupported one. " + style_notes)
    user = (f"Section: {section_title}\nWhat it must establish: {intent}\n\n"
            f"Evidence available (use only this; do not invent):\n{evidence}")
    return llm.complete(system, user)


def humanise(llm: LLM, text: str) -> str:
    """A naturalness pass — loosen stiff sentences without changing a number or a claim.
    Used sparingly; on already-clean prose it should return the text nearly unchanged."""
    system = (
        "Loosen any sentence that is technically fine but stiff, so it reads as a person "
        "wrote it. Do NOT change any number, citation, symbol, or claim. Do NOT remove the "
        "AI-assistance disclosure or alter the Methods. If a passage is already natural, "
        "leave it. Return the full text.")
    return llm.complete(system, text)
