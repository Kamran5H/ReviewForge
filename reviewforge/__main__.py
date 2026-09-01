"""Command-line entry: python -m reviewforge <command> <project> [options]."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from .config import Config
from .scaffold import init_project


def _usage():
    print(__doc__)
    print("""
commands:
  init   <project>                 scaffold a new review project + config.yaml
  run    <project> --stage NAME    run one pipeline stage
  sample <project>                 dump the validation sample to read (validate step)
  score  <project>                 score reader verdicts -> agreement + kappa
  check  <project>                 validate config.yaml before running

stages: harvest cache screen validate draft figures compile verify
""")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        _usage(); return 0
    cmd = argv[0]

    if cmd == "init":
        if len(argv) < 2:
            print("init needs a project name"); return 1
        init_project(argv[1]); return 0

    if len(argv) < 2:
        print(f"{cmd} needs a project directory"); return 1
    project = Path(argv[1])

    if cmd == "check":
        problems = Config.load(project / "config.yaml").validate()
        if problems:
            print("config problems:")
            for p in problems:
                print("  -", p)
            return 1
        print("config OK"); return 0

    from .pipeline import Pipeline
    pipe = Pipeline(project)

    if cmd == "run":
        stage = None
        if "--stage" in argv:
            stage = argv[argv.index("--stage") + 1]
        if not stage:
            print("run needs --stage NAME"); return 1
        print(pipe.run(stage)); return 0

    if cmd == "sample":
        from . import validate
        an = project / "analysis"
        rep = json.loads((an / "screen.json").read_text(encoding="utf-8"))
        idx = json.loads((project / "textcache" / "_index.json").read_text(encoding="utf-8"))
        cfg = pipe.cfg
        # sample the first configured subset that excludes reviews, else the first
        subset = next((s for s in cfg.subsets if s.exclude_reviews), cfg.subsets[0])
        sc = __import__("reviewforge.screen", fromlist=["Screen"]).Screen(cfg, project / "textcache")
        sample = validate.draw_sample(rep["records"], lambda r: sc.in_subset(r, subset),
                                      cfg.validation_sample, cfg.validation_seed)
        item = cfg.screen_items[0]
        validate.dump_for_reading(sample, project / "textcache", idx, item.key,
                                  item.patterns, an / "sample_to_read.txt")
        (an / "sample_index.json").write_text(json.dumps(
            [{"file": r["file"], "auto": r.get(item.key)} for r in sample],
            indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {len(sample)} papers to analysis/sample_to_read.txt for the "
              f"'{item.label}' question. Read them, record verdicts in analysis/verdicts.json "
              f"as [{{\"file\":..,\"auto\":..,\"reader\":\"yes|no|not_applicable\",\"note\":..}}], "
              f"then: python -m reviewforge score {project}")
        return 0

    if cmd == "score":
        from . import validate
        an = project / "analysis"
        verdicts = json.loads((an / "verdicts.json").read_text(encoding="utf-8"))
        item = pipe.cfg.screen_items[0]
        result = validate.score(verdicts, item.key)
        (an / "validation.json").write_text(json.dumps(result, indent=1, ensure_ascii=False),
                                            encoding="utf-8")
        print(f"agreement {result['agreement_pct']}%  kappa {result['kappa']}  "
              f"| reader finds {result['reader_finding_pct']}% "
              f"(95% CI {result['reader_finding_ci']})  "
              f"| not-applicable {result['not_applicable']}/{result['n_sample']}")
        print(result["note"])
        return 0

    _usage(); return 1


if __name__ == "__main__":
    sys.exit(main())
