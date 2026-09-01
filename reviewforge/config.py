"""Per-project configuration — what makes ReviewForge topic-agnostic.

Everything specific to a review (its subject, its search terms, its section plan, the
parameters its screen looks for, the LLM backend) lives in one YAML file. The engine reads
this and nothing else about the topic; there is no zinc-air anywhere in the code paths.
"""
from __future__ import annotations
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class ScreenItem:
    """One thing the reproducible screen looks for in every paper.

    `patterns` are regexes; a paper scores positive if any matches. `window` (chars) and
    `context_terms` optionally require the match to sit near a topic term, which is how the
    zinc-air screen distinguished a cell's atmosphere from a furnace step. Set
    `lower_bound=True` (the default) so the reported rate is always labelled as a floor.
    """
    key: str
    label: str
    patterns: list[str]
    window: int = 0
    context_terms: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    lower_bound: bool = True


@dataclass
class Subset:
    """A named slice of the corpus with a single lexical criterion. Every percentage the
    review quotes is tied to one of these, and its denominator is stated wherever it is used
    (the zinc-air project's Table 1)."""
    name: str
    min_topic_hits: int = 2
    require_full_context: bool = False
    exclude_reviews: bool = False


@dataclass
class SectionPlan:
    number: str
    title: str
    intent: str                       # one line: what this section must establish
    evidence_keys: list[str] = field(default_factory=list)   # screen items it draws on


@dataclass
class LLMConfig:
    backend: str = "ollama"           # ollama | openai | anthropic | none
    model: str = "llama3.1"
    base_url: str = "http://localhost:11434"
    api_key_file: str = ""            # path; never inline a key
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class Config:
    # identity
    topic: str = "REQUIRED: the review's subject, e.g. 'solid-state electrolytes'"
    title: str = ""
    authors: list[str] = field(default_factory=list)
    affiliation: str = ""
    corresponding: str = ""           # email — inserted only by the author, never invented

    # retrieval
    query: str = ""                   # the exact search string; recorded verbatim in Methods
    topic_terms: list[str] = field(default_factory=list)   # for the relevance gate + windows
    competing_terms: list[str] = field(default_factory=list)  # adjacent fields to exclude
    year_start: int = 2015
    year_end: int = 2025
    max_papers: int = 500
    apis: list[str] = field(default_factory=lambda: [
        "openalex", "semantic_scholar", "europepmc", "doaj", "core", "arxiv"])

    # analysis
    subsets: list[Subset] = field(default_factory=list)
    screen_items: list[ScreenItem] = field(default_factory=list)
    validation_sample: int = 60       # papers to read by hand; never 0
    validation_seed: int = 20240101   # fix it so the sample is reproducible

    # writing
    sections: list[SectionPlan] = field(default_factory=list)
    target_journal: str = ""

    # infrastructure
    llm: LLMConfig = field(default_factory=LLMConfig)
    project_dir: str = "."

    # ---- io ----
    @staticmethod
    def load(path: str | Path) -> "Config":
        if yaml is None:
            sys.exit("pyyaml is required: pip install pyyaml")
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return Config._from_dict(raw)

    @staticmethod
    def _from_dict(d: dict) -> "Config":
        c = Config()
        for k, v in d.items():
            if k == "llm" and isinstance(v, dict):
                c.llm = LLMConfig(**v)
            elif k == "subsets":
                c.subsets = [Subset(**x) for x in v]
            elif k == "screen_items":
                c.screen_items = [ScreenItem(**x) for x in v]
            elif k == "sections":
                c.sections = [SectionPlan(**x) for x in v]
            elif hasattr(c, k):
                setattr(c, k, v)
        return c

    def save(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(asdict(self), sort_keys=False,
                                             allow_unicode=True), encoding="utf-8")

    def validate(self) -> list[str]:
        """Return a list of problems; empty means ready to run."""
        problems = []
        if not self.query:
            problems.append("config.query is empty — the exact search string is required "
                            "and is recorded verbatim in the Methods.")
        if not self.topic_terms:
            problems.append("config.topic_terms is empty — the relevance gate needs them.")
        if self.validation_sample < 30:
            problems.append("validation_sample < 30 — the zinc-air project found 30 is the "
                            "floor for a defensible agreement rate; do not go lower.")
        if not self.screen_items:
            problems.append("no screen_items — nothing to measure about reporting practice.")
        if self.corresponding and "@" not in self.corresponding:
            problems.append("corresponding looks malformed.")
        return problems
