#!/usr/bin/env python3
"""Every artefact path resolves through `paths`, or this exits non-zero.

`paths.py` declares one variable per artefact — `DB`, `REGISTRY`, `RAW`,
`SCRATCH`, `DASHBOARD`, `PLUGINS`, `KEY_FILE` — and every one of them is
overridable by an environment variable. That is not a convenience: it is the
project's TESTABILITY CONTRACT. A test that cannot redirect an input has to
either run against the live estate or not run at all, and both have happened
here.

WHY THIS IS A SCRIPT AND NOT A THIRD COMMENT. The same defect was found and
fixed by hand six times in one sitting, each time by a different route:

  1. `tools/notify_findings.py` opened `paths.STORE / "observatory.db"`, so the
     notification suite wrote two fixture rows into the LIVE ledger. Both had to
     be found and deleted by hand.
  2. `tools/validate_registry.py` resolved the Namecheap export from `ROOT` —
     four lines below a comment explaining that exact bug about its neighbour —
     so a sandboxed registry was validated against the live registrar CSV.
  3. `survey.py`'s `_collector_degradation` read `ROOT / "store" / "raw"`, which
     is why the GitHub degradations reached no reader for as long as they did.
  4. `survey.py` again, at the domain notice, twelve lines from its own fixed
     comment.
  5. `collectors/scan_bitbucket.py` and `collectors/scan_remotes.py`, both
     reading `local.json` from `ROOT`.
  6. `collectors/emit_registry.py`, reading the liveness file from `ROOT`.

A rule that has to be remembered six times is not a rule. The check is
deliberately syntactic — it looks for path CONSTRUCTION, not for the strings
themselves, so a docstring showing `scan_domains.py store/raw/domains_live.json`
as usage passes, and an argv element in the gate's own step table passes too:
those are arguments a caller supplies, which is exactly the seam that works.

    tools/check_paths.py            # non-zero on any violation

TO ALLOW ONE DELIBERATELY, put the marker on the same line with a reason:

    x = ROOT / "store" / "raw"     # paths-check: allow — <why>
"""
from __future__ import annotations
import ast, io, pathlib, re, sys, tokenize

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOW = "paths-check: allow"

#: (pattern, what to use instead, the defect it comes from). Each rule is here
#: because it was measured, not because it might happen.
RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r'/\s*"store"\s*/\s*"raw"'), "paths.SCRATCH",
     "the collector output directory; six sites resolved it from ROOT"),
    (re.compile(r'(?:Path|open)\(\s*f?"store/raw'), "paths.SCRATCH",
     "same directory, built as a relative string"),
    (re.compile(r'else\s+f?"store/raw'), "paths.SCRATCH",
     "a relative default output path — scan_github.py wrote ten owner listings "
     "into store/raw/github, which nothing reads"),
    (re.compile(r'(?:STORE|ROOT)\s*/\s*"observatory\.db"'), "paths.DB",
     "the ledger; notify_findings.py wrote fixture rows into the live store"),
    (re.compile(r'/\s*"store"\s*/\s*"observatory\.db"'), "paths.DB",
     "the same, spelled out"),
    (re.compile(r'ROOT\s*/\s*"registry"'), "paths.REGISTRY",
     "the canonical fact base; a sandboxed registry must be redirectable"),
    # THE SAME BASE, SPELLED AS A RELATIVE STRING. The rule above matches a path
    # built from ROOT and missed `Path("registry/projects.json")` entirely — a
    # plugin written from `plugins/README.md` on 2026-09-08 used exactly that,
    # because the document said the script runs "from the repository root" and
    # never that a resolver exists.
    (re.compile(r'(?:Path|open)\(\s*f?"registry/'), "paths.REGISTRY",
     "the registry as a relative string; a sandboxed registry must be "
     "redirectable however the path is spelled"),
    # THE ESTATE ROOT, which had no rule at all while `paths.DATA` existed for
    # it. The same plugin resolved it as `Path.home() / "DATA"`, which is right
    # on this machine and on no other, and the gate that exists to catch exactly
    # that said 0 violations.
    (re.compile(r'home\(\)\s*/\s*"DATA"'), "paths.DATA",
     "the estate root; a machine that keeps its projects elsewhere is the case "
     "the resolver exists for"),
                                                                                   
                                                                                 
                                                                                
                                                                                 
                                                                        
                 
    (re.compile(r'/\s*"registry"\s*/\s*"_raw"'), "paths.RAW",
     "the registrar exports the validator compares against"),
    # NOT a path rule, and it is here because this is the file the gate already
    # runs over every source. `tempfile.mkdtemp` never removes its directory —
    # that is its whole difference from `TemporaryDirectory` — and 98 call sites
    # across 42 suites took one `./observatory.py check` run from 607 MiB free to
    # 317 MiB, on a volume that reads 100% full. The run before that died with
    # `no space left on device`. `tests/tmp.mkdtemp` registers cleanup at exit.
    (re.compile(r'tempfile\.mkdtemp\('), "tests/tmp.mkdtemp (imported as `tmpdir`)",
     "mkdtemp leaves its directory behind; a gate that cannot run twice is not "
     "a gate"),
]

#: file -> why it cannot be scanned by the rule it carries. A dict rather than a
#: set, like every other exemption list here: a bare name is indistinguishable
#: from an oversight, and the next reader cannot tell whether removing it fixes
#: something or breaks something.
EXEMPT_FILES = {
    "paths.py": "it is where the overridable variables are DEFINED",
    "tools/check_paths.py": "it quotes every pattern it hunts for",
    "tests/tmp.py": "it WRAPS `tempfile.mkdtemp` — being the one place that "
                    "calls it is the point of the file",
}


def prose_removed(src: str) -> str:
    """The source with COMMENTS and DOCSTRINGS blanked in place.

    Not `tests/source_reader.code_only`, and the difference is the whole reason
    this function exists: that one blanks every string literal, and these rules
    are *made of* string literals — `/ "store" / "raw"` is two STRING tokens. It
    would report a clean repository for ever.

                                                                             
                                                                     
                                                           
                                                                                
                                                                          
                                                                          
                         

    Blanked in place, so the reported line number is the real one.
    """
    grid = [list(l) for l in src.splitlines(keepends=True)]

    def blank(r1: int, c1: int, r2: int, c2: int) -> None:
        for row in range(r1 - 1, min(r2, len(grid))):
            line = grid[row]
            start = c1 if row == r1 - 1 else 0
            end = c2 if row == r2 - 1 else len(line)
            for col in range(start, min(end, len(line))):
                if line[col] != "\n":
                    line[col] = " "

    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            blank(tok.start[0], tok.start[1], tok.end[0], tok.end[1])
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            d = body[0].value
            blank(d.lineno, d.col_offset, d.end_lineno, d.end_col_offset)
    return "".join("".join(l) for l in grid)


def sources() -> list[pathlib.Path]:
    out = []
    for f in sorted(ROOT.rglob("*.py")):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "node_modules/", "store/raw/")):
            continue
        if rel in EXEMPT_FILES:
            continue
        out.append(f)
    return out


def main() -> int:
    bad: list[str] = []
    allowed = 0
    for f in sources():
        rel = f.relative_to(ROOT).as_posix()
        raw = f.read_text(encoding="utf-8")
        try:
            code = prose_removed(raw)
        except (SyntaxError, tokenize.TokenError, IndentationError) as exc:
            # A file that will not parse is a different failure, and reading it
            # raw would let its comments be flagged. Say so rather than skip it.
            bad.append(f"{rel}: cannot be read as Python: {type(exc).__name__}: {exc}")
            continue
        # The marker lives in a comment, which `prose_removed` blanks — so the
        # pattern is matched against the CODE view and the marker against the
        # original line. Reading both from the blanked copy would make every
        # exemption unreachable, which is the same defect as an assertion that
        # can only be satisfied by prose.
        for n, (line, shown) in enumerate(zip(code.splitlines(),
                                              raw.splitlines()), 1):
            for pat, use, why in RULES:
                if not pat.search(line):
                    continue
                if ALLOW in shown:
                    allowed += 1
                    continue
                bad.append(f"{rel}:{n}: resolve this through {use} — {why}\n"
                           f"    {shown.strip()[:110]}")
                break
    for b in bad:
        print(b)
    print(f"checked {len(sources())} python files; {len(bad)} violation(s); "
          f"{allowed} allowed by marker")
    if bad:
        print("\nEach of these is an input a test cannot redirect. Six were found by "
              "hand in one sitting; this check exists so the seventh is found here.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
