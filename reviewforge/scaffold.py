"""Project scaffolding — `python -m reviewforge init <name>` writes a ready-to-edit config.

The example config is a DIFFERENT topic (perovskite solar-cell stability) precisely to show
that nothing about the engine is zinc-air-specific. Edit it to your subject and run.
"""
from __future__ import annotations
from pathlib import Path

EXAMPLE_CONFIG = """# ReviewForge project configuration
# Edit every field for your topic. Nothing here is engine-specific.

topic: "operational stability of perovskite solar cells"
title: ""                      # leave blank; propose after the thesis is found
authors: ["Your Name"]
affiliation: "Your Department, Your University"
corresponding: ""              # your email — you insert this, never the engine

# --- retrieval ---
query: "perovskite solar cell stability"          # recorded VERBATIM in the Methods
topic_terms: ["perovskite", "PSC", "solar cell", "photovoltaic"]
competing_terms: ["silicon solar", "organic photovoltaic", "dye-sensitized", "CIGS"]
year_start: 2016
year_end: 2025
max_papers: 500
apis: ["openalex", "semantic_scholar", "europepmc", "doaj", "core", "arxiv"]

# --- subsets: every quoted percentage is tied to one of these ---
subsets:
  - {name: "Retrieved corpus", min_topic_hits: 0}
  - {name: "Primary device studies", min_topic_hits: 3, require_full_context: true, exclude_reviews: true}
  - {name: "Reporting-standard subset", min_topic_hits: 2, require_full_context: true}

# --- screen items: what you measure about reporting practice ---
# window>0 requires the match to sit near a topic term (avoids false positives).
screen_items:
  - key: "atmosphere"
    label: "Measurement atmosphere stated (N2 / ambient / controlled)"
    patterns: ["\\\\bN2 glovebox\\\\b", "ambient (?:air|conditions)", "controlled atmosphere", "relative humidity of \\\\d"]
    window: 220
    context_terms: ["perovskite", "device", "cell"]
    exclude_terms: ["glovebox for synthesis"]
  - key: "illumination_protocol"
    label: "Stability test illumination and spectrum stated"
    patterns: ["AM1\\\\.5", "\\\\b1 sun\\\\b", "continuous illumination", "maximum power point"]
    window: 200
    context_terms: ["stability", "aging", "degradation"]
  - key: "encapsulation"
    label: "Encapsulation stated (or its absence)"
    patterns: ["encapsulat", "unencapsulated", "glass-glass"]
  - key: "iso_standard"
    label: "ISOS stability protocol cited"
    patterns: ["ISOS[- ]?[LDOT]", "consensus stability"]
  - key: "t80_reported"
    label: "T80 / lifetime metric reported"
    patterns: ["\\\\bT80\\\\b", "\\\\bTS80\\\\b", "time to 80%"]

validation_sample: 60          # papers to READ by hand; never below 30
validation_seed: 20240101      # fix it so the sample is reproducible

# --- section plan ---
sections:
  - {number: "1", title: "Introduction", intent: "State the gap between record efficiency and reported operational lifetime.", evidence_keys: ["t80_reported"]}
  - {number: "2", title: "Degradation mechanisms", intent: "The intrinsic and extrinsic pathways, and which the test protocols actually probe.", evidence_keys: ["atmosphere", "illumination_protocol"]}
  - {number: "3", title: "Stability metrics and protocols", intent: "What the field measures, where it misleads, and a reporting standard.", evidence_keys: ["iso_standard", "encapsulation", "t80_reported"]}
  - {number: "4", title: "The unresolved problem", intent: "The condition set no reported device satisfies at once.", evidence_keys: []}
  - {number: "5", title: "Methods", intent: "Full disclosure of the screen, its validation and its limits.", evidence_keys: []}

target_journal: ""

# --- LLM backend for the judgement stages ---
llm:
  backend: "ollama"            # ollama | openai | anthropic | none
  model: "llama3.1"
  base_url: "http://localhost:11434"
  api_key_file: ""             # path to a file holding the key; never inline it
  temperature: 0.3
  max_tokens: 4096
"""

REQUIREMENTS = """rapidfuzz>=3.0
requests>=2.28
pymupdf>=1.23
python-docx>=1.1
matplotlib>=3.7
pyyaml>=6.0
"""


def init_project(name: str) -> None:
    root = Path(name)
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(EXAMPLE_CONFIG, encoding="utf-8")
    for sub in ("corpus", "textcache", "analysis", "sections", "figures", "output"):
        (root / sub).mkdir(exist_ok=True)
    (root / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    print(f"Scaffolded {root}/")
    print("  1. edit config.yaml for your topic")
    print("  2. python -m reviewforge check", name)
    print("  3. python -m reviewforge run", name, "--stage harvest")
