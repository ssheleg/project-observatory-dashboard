#!/usr/bin/env python3
"""Which trap is guarded by which test — derived, never typed.

`docs/knowledge-pack.md` is this repository's registry of recorded failures: a
trap is a defect that happened, and each row promises a planted fixture that
would have caught it. The promise was kept by hand, and the hand-written half
drifted several ways at once:

* some traps never reached the "what is checked where" table at all;
* others existed only as tests, declared in no row;
* the summary sentence claimed a count that no longer matched what was guarded;
* the table's file names went stale as guards moved between test files;
* and one row still instructed a fixture the system now deliberately REFUSES,
  because a later decision inverted it.

None of that is carelessness. A table of dozens of rows maintained by hand
beside code that moves daily is a promise nobody can keep, which is why the
mapping is now DERIVED: a guard declares its own trap in its docstring:

    def test_a_frozen_clock_still_yields_distinct_ids() -> None:
        \"\"\"Trap: T12 — the whole defect is two runs inside one second.\"\"\"

— and this tool reads the declarations, compares them with the traps the pack
declares, and writes the table between the two markers in the document.

**What the derivation proves, and what it does not.** It proves ATTRIBUTION
(every trap has a named guard, every guard names a declared trap) and
REACHABILITY: the guard's file is run by a gate step, and the function is
dispatched from its suite's `__main__` rather than defined and forgotten. It
does NOT prove EFFICACY. A guard that can no longer fire passes every check
here. Efficacy is established the way it always is in this repository: by
watching the check reject a planted defect.

    tools/trap_map.py            the mapping, and what is unguarded
    tools/trap_map.py --check    exit non-zero on any drift
    tools/trap_map.py --write    regenerate the table in the knowledge pack
"""
from __future__ import annotations
import argparse
import ast
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                      # noqa: E402

PACK = ROOT / "docs/knowledge-pack.md"
BEGIN = "<!-- trap-map:begin -->"
END = "<!-- trap-map:end -->"
#: `Trap: T12` or `Traps: T22, T23`, anywhere in a docstring.
MARKER = re.compile(r"^\s*Traps?:\s*(T\d+(?:\s*,\s*T\d+)*)\s*(?:—.*)?$", re.M)


def declared() -> dict[str, str]:
    """Every trap the pack declares, id -> its bold title."""
    out: dict[str, str] = {}
    for tid, title in re.findall(r"^\| (T\d+) \| \*\*(.+?)\.\*\*", PACK.read_text("utf-8"), re.M):
        out[tid] = title
    return out


def _dispatched(tree: ast.Module) -> set[str]:
    """Names referenced inside `if __name__ == "__main__"`.

    A suite here dispatches by listing its functions; one that is defined and
    not listed runs never and reports nothing, which is a guard that cannot
    fire in its purest form.
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.If) and any(
                isinstance(c, ast.Name) and c.id == "__name__" for c in ast.walk(node.test)):
            names |= {s.id for s in ast.walk(node) if isinstance(s, ast.Name)}
    return names


def guards() -> list[dict]:
    """Every declaration of a trap in a test, with what can be checked about it."""
    out: list[dict] = []
    for path in sorted(ROOT.glob("tests/*.py")):
        src = path.read_text("utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        live = _dispatched(tree)
        rel = path.relative_to(ROOT).as_posix()
        for node in [tree] + [n for n in tree.body
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            doc = ast.get_docstring(node) or ""
            for m in MARKER.finditer(doc):
                for tid in re.findall(r"T\d+", m.group(1)):
                    where = getattr(node, "name", None)
                    out.append({"trap": tid, "file": rel, "function": where,
                                "dispatched": where is None or where in live})
    return out


def steps_by_file() -> dict[str, list[str]]:
    """file -> the gate steps that run it, read from `observatory.py` itself."""
    spec = importlib.util.spec_from_file_location("obs_for_traps", ROOT / "observatory.py")
    obs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obs)
    in_check = set(obs.GROUPS["check"])
    out: dict[str, list[str]] = {}
    for step, cmd in obs.STEPS.items():
        for part in cmd:
            if isinstance(part, str) and part.endswith(".py") and step in in_check:
                out.setdefault(part, []).append(step)
    return out


def report() -> tuple[dict, list[str]]:
    """The mapping and every drift in it, as data."""
    decl, found, steps = declared(), guards(), steps_by_file()
    by_trap: dict[str, list[dict]] = {}
    for g in found:
        by_trap.setdefault(g["trap"], []).append(g)
    drift: list[str] = []
    for tid in decl:
        if tid not in by_trap:
            drift.append(f"{tid} is declared in the pack and no test declares it")
    for tid, gs in sorted(by_trap.items(), key=lambda kv: int(kv[0][1:])):
        if tid not in decl:
            drift.append(f"{tid} is guarded by {gs[0]['file']} and the pack declares no such trap")
        for g in gs:
            if not g["dispatched"]:
                drift.append(f"{tid}: {g['file']}:{g['function']} is never dispatched from "
                             "its suite's __main__")
            if g["file"] not in steps:
                drift.append(f"{tid}: {g['file']} is run by no step of the `check` group")
    return {"declared": decl, "by_trap": by_trap, "steps": steps}, drift


def efficacy() -> dict[str, str]:
    """How each trap's guard was WATCHED failing, read from the sweep's registry.

    Attribution is derived here; efficacy is derived there. The column exists
    because a reader of the table asks the second question the moment the first
    is answered — and because an empty cell is then a visible gap rather than a
    silence. Loaded lazily: a missing tool degrades to an empty column instead
    of taking the whole derivation down.
    """
    try:
        spec = importlib.util.spec_from_file_location("eff_map", ROOT / "tools/trap_efficacy.py")
        eff = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(eff)
    except Exception:
        return {}
    out = {t: "self-driven" for t in eff.SELF_DRIVEN}
    for m in eff.MUTATIONS:
        out[m["trap"]] = "mutation"
    return out


def table(data: dict) -> str:
    """The generated block: one row per trap, in the order the pack declares them."""
    steps = data["steps"]
    eff = efficacy()
    lines = [BEGIN,
             "",
             "| Trap | Guarded by | Step | Efficacy |",
             "|---|---|---|---|"]
    for tid in sorted(data["declared"], key=lambda t: int(t[1:])):
        gs = data["by_trap"].get(tid, [])
        where = "<br>".join(
            f"`{g['file']}`" + (f" · `{g['function']}`" if g["function"] else "")
            for g in gs) or "**nothing**"
        step = ", ".join(sorted({s for g in gs for s in steps.get(g["file"], [])})) or "—"
        lines += [f"| {tid} | {where} | {step} | {eff.get(tid, '**unmeasured**')} |"]
    n_traps = len(data["declared"])
    n_guards = sum(len(v) for v in data["by_trap"].values())
    lines += ["",
              f"**{n_traps} traps, {n_guards} guards, and every row above is derived** by "
              "`tools/trap_map.py` from the `Trap:` line each guard carries in its own "
              "docstring — the table is regenerated, never edited. It proves attribution "
              "and reachability: the trap has a named guard, the guard names a declared "
              "trap, its file is run by a step of the `check` group, and the function is "
              "dispatched from its suite's `__main__`. It does not prove efficacy — that "
              "is established by watching a check reject a planted defect, and a guard "
              "that has stopped being able to fire would pass every test here. "
              "The last column names how efficacy IS established for each trap — "
              "`mutation` means `tools/trap_efficacy.py` puts the defect back and "
              "watches this guard fail; `self-driven` means the guard plants the "
              "defect itself. Neither is claimed by this table: run the sweep.",
              "",
              END]
    return "\n".join(lines)


def write(data: dict) -> bool:
    text = PACK.read_text("utf-8")
    new = table(data)
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        out = head + new + tail
    else:
        raise SystemExit(f"{PACK} carries no {BEGIN} … {END} block to write into")
    if out == text:
        return False
    atomic.write_text(PACK, out)
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or 'Inspect local diagnostic coverage.').splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit non-zero on any drift")
    ap.add_argument("--write", action="store_true", help="regenerate the table in the pack")
    args = ap.parse_args(argv[1:])
    data, drift = report()
    if args.write:
        changed = write(data)
        print(f"{PACK.relative_to(ROOT)} {'rewritten' if changed else 'already current'}")
    else:
        for tid in sorted(data["declared"], key=lambda t: int(t[1:])):
            gs = data["by_trap"].get(tid, [])
            print(f"  {tid:5} {len(gs)} guard(s)  " +
                  ", ".join(f"{g['file']}:{g['function']}" for g in gs))
    if drift:
        print(f"\n{len(drift)} drift(s):")
        for d in drift:
            print("  -", d)
        if args.check:
            return 1
    elif args.check:
        print(f"trap map current: {len(data['declared'])} trap(s), "
              f"{sum(len(v) for v in data['by_trap'].values())} guard(s)")
    if args.check and BEGIN in PACK.read_text("utf-8"):
        if table(data) not in PACK.read_text("utf-8"):
            print("  - the table in docs/knowledge-pack.md is not what the code derives; "
                  "run tools/trap_map.py --write")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
