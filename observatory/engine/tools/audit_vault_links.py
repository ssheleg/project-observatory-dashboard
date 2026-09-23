#!/usr/bin/env python3
"""Find wikilinks in the wiki that resolve to nothing.

Three things a naive check gets wrong, and each one produced a false positive the
first time this was run by hand:

* **An anchor is not part of the path.** `[[note#Section]]` points at `note`;
  appending `.md` to the whole string finds nothing and reports a healthy link
  as broken. Most of the first "dangling" links were this.
* **A link can be prose.** `use full-path [[wikilinks]]` in a README is
  documentation about the syntax, not a link — but it parses as one. Whether
  that is a defect is a judgement, so it is reported separately rather than
  counted as broken.
* **An escaped pipe is not a path.** `[[path\\|label]]` escapes the `|` because
  the link sits inside a Markdown table, where a bare pipe breaks the cell. Read
  naively the target becomes `path\\` and resolves to nothing.

All three were found by this checker reporting healthy links as broken. A vault
can show several "broken" links and actually have none — which is the more
useful finding, and the reason this file exists rather than a one-off sweep.

The archive directory is skipped by default: a dated snapshot pointing at notes
that existed on its date is what a snapshot IS, and rewriting one destroys the
thing it was taken for. `--include-archives` says so out loud when you want the
count.
"""
from __future__ import annotations
import argparse, collections, json, pathlib, re, sys
from datetime import datetime, timezone

LINK = re.compile(r"\[\[([^\]|]+?)(?:\\?\|[^\]]*)?\]\]")
#: Inline code spans. `[[wikilinks]]` inside backticks is documentation ABOUT the
#: syntax, not a link, and counting it as broken is how an auditor cries wolf.
CODE = re.compile(r"`[^`\n]*`")


def vault_root(explicit: str | None) -> pathlib.Path:
    if explicit:
        return pathlib.Path(explicit).expanduser()
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import paths
    return paths.VAULT


def basenames(root: pathlib.Path) -> dict[str, list[str]]:
    """basename -> every note with it. What Obsidian resolves a bare name by.

    Obsidian resolves `[[deep-note]]` to `projects/x/deep-note.md` wherever it
    lives; a checker that only tries `root/deep-note.md` reports a link the
    ACTUAL wiki follows as "bare name — may be prose about wikilink syntax".
    That is a false positive of the exact kind the top of this file was written
    about, and it makes the ambiguous bucket useless — a genuine prose mention
    and a working link land in it together.
    """
    out: dict[str, list[str]] = {}
    for f in root.rglob("*.md"):
        out.setdefault(f.stem, []).append(str(f.relative_to(root)))
    return out


def resolve(root: pathlib.Path, target: str,
            index: dict[str, list[str]] | None = None) -> tuple[bool, str]:
    """(exists, why_not). The anchor is stripped before resolution."""
    raw = target.strip()
    path = raw.split("#", 1)[0].strip()
    if not path:
        return True, "anchor-only, resolves to the same file"
    if path.startswith(("http://", "https://", "mailto:")):
        return True, "external"
    # `[[path\|label]]` — the pipe is escaped because the link sits inside a
    # Markdown table, where a bare | breaks the cell. The backslash belongs to
    # the escape, not to the path. This was the third false positive in a row
    # from a checker written faster than the thing it was checking.
    path = path.rstrip("\\")
    if (root / (path + ".md")).exists() or (root / path).exists():
        return True, ""
    if "/" not in path:
        # THREE OUTCOMES for a bare name, because Obsidian resolves one by
        # basename anywhere in the vault and this used to have only two.
        hits = (index or {}).get(path, [])
        if len(hits) == 1:
            return True, f"bare name, resolved by basename to {hits[0]}"
        if len(hits) > 1:
            # Obsidian picks by proximity, so which note this means depends on
            # where the link sits. A working link, and still worth saying.
            return False, (f"bare name matching {len(hits)} notes "
                           f"({', '.join(sorted(hits)[:3])}…) — Obsidian resolves it "
                           f"by proximity, so it means different things from "
                           f"different files")
        return False, "bare name matching no note — prose about the syntax, or broken"
    return False, "no such note"


def report(**fields) -> None:
    """The receipt, and the reason this file gained one.

    Nothing read this tool's output. It is not in the gate and not in the tick,
    while `tools/commit_projection.py` writes into that same wiki on every tick
    — so the one thing that can break a wikilink ran constantly and the checker
    for it ran only when a person typed it. A broken link would have waited for
    somebody to be curious.

    Written on EVERY path, an absent vault included: a stale receipt saying
    `clean` is worse than none, because `tools/build_findings.py` believes it.
    """
    doc = {"ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **fields}
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
        import atomic
        import paths
        atomic.write_json(paths.SCRATCH / "vault-links.json", doc)
    except Exception as exc:                                    
        print(f"the receipt could not be written: {type(exc).__name__}: {exc}",
              file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default=None)
    ap.add_argument("--include-archives", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="exit code only")
    a = ap.parse_args()
    root = vault_root(a.vault)
    if not root.is_dir():
        # COULD NOT MEASURE, not "the links are broken". This used to return 1,
        # so on any machine but the one holding the wiki — CI, a fresh clone,
        # another operator — the tool was red for a reason that has nothing to do
        # with a link. The same exit code for a fact about the run and a fact
        # about the subject also made the step unusable anywhere else.
        print(f"no wiki at {root} — nothing was checked", file=sys.stderr)
        report(outcome="vault-absent", broken=None, ambiguous=None, notes=0,
               links=0, detail=f"no directory at {root}")
        return 0

    index = basenames(root)
    broken: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    total_links = files = 0
    for f in sorted(root.rglob("*.md")):
        # A PATH COMPONENT, not a substring. A substring test on the whole path
        # also skips a note whose own filename happens to contain the archive
        # directory's name, and any note under a directory whose name merely
        # contains the word — a silent exclusion from a checker whose whole
        # output is a count.
        if not a.include_archives and "_archives" in f.relative_to(root).parts:
            continue
        files += 1
        text = f.read_text(encoding="utf-8", errors="replace")
        # Blank out code spans so their contents cannot parse as links.
        text = CODE.sub(lambda m: " " * len(m.group(0)), text)
        for m in LINK.finditer(text):
            total_links += 1
            ok, why = resolve(root, m.group(1), index)
            if not ok:
                broken[m.group(1)].append((str(f.relative_to(root)), why))

    prose = {t: v for t, v in broken.items() if v[0][1].startswith("bare name")}
    real = {t: v for t, v in broken.items() if not v[0][1].startswith("bare name")}
    if not a.quiet:
        print(f"{files} note(s), {total_links} wikilink(s)"
              + ("" if a.include_archives else ", _archives skipped"))
        print(f"  broken:        {sum(len(v) for v in real.values())} "
              f"in {len(real)} target(s)")
        print(f"  ambiguous:     {sum(len(v) for v in prose.values())} "
              f"bare name(s) that may be prose")
        for label, group in (("BROKEN", real), ("AMBIGUOUS", prose)):
            if not group:
                continue
            print(f"\n{label}")
            for t, occurrences in sorted(group.items(), key=lambda x: -len(x[1])):
                print(f"  -> {t}    [{occurrences[0][1]}]")
                for src, _ in occurrences[:4]:
                    print(f"       {src}")
                if len(occurrences) > 4:
                    print(f"       … and {len(occurrences) - 4} more")
    report(outcome="broken-links" if real else "clean",
           broken=sum(len(v) for v in real.values()),
           ambiguous=sum(len(v) for v in prose.values()),
           notes=files, links=total_links,
           detail="; ".join(f"{t} [{v[0][1][:60]}]" for t, v in
                            sorted(real.items())[:5]) or "every wikilink resolves",
           targets=sorted(real))
    return 1 if real else 0


if __name__ == "__main__":
    raise SystemExit(main())
