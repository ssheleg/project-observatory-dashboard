#!/usr/bin/env python3
"""Writes that land whole or not at all.

`json.dump(rows, open(path, "w"))` opens the destination for writing —
**truncating it** — and only then begins serialising. A crash, a full disk or a
killed process between those two moments leaves a file that is empty or half a
document, and the next stage does one of two things with it: fail on a
JSONDecodeError, or, if the truncation happened to land on `[]`, read it as a
valid empty result.

The second is the dangerous one. `collectors/merge.py` consumes collector output
and `emit_registry.py` rewrites `registry/*.json` from the result — so an empty
`local.json` is indistinguishable from "this machine has no projects", and the
registry loses them. Nothing in the pipeline would say why: `tick.sh` stops only
on a non-zero exit, and a scan that wrote an empty file successfully has none.

A nearly full disk is the ordinary way this happens, not an exotic one.

    write_json(path, data)            serialise to a sibling temp file, fsync, rename
    write_json_carrying(path, doc)    the same, keeping a stamp when nothing moved
    write_text(path, text)            the same guarantee for text that is not JSON
"""
from __future__ import annotations
import errno, json, os, pathlib, shutil, tempfile
from typing import Any


def write_json(path: str | os.PathLike, data: Any, *, indent: int = 1,
               ensure_ascii: bool = False) -> pathlib.Path:
    """Serialise first, replace second. The destination is never truncated.

    The temp file is created in the SAME directory, because `os.replace` is
    atomic only within one filesystem — a temp in `/tmp` would make this a copy
    across devices and reintroduce the partial write it exists to prevent."""
    dest = pathlib.Path(path)
    # Refuse future registry versions and retain optional extension fields.
    import configuration
    import paths
    if dest.parent.resolve() == paths.REGISTRY.resolve() and dest.suffix == ".json":
        configuration.validate_registry_document(dest, data)
        if dest.exists():
            old = configuration.read_json(dest)
            configuration.validate_registry_document(dest, old)
            data = {**old, **data}
    if any(p.is_symlink() for p in (dest, *dest.parents)):
        raise ValueError("Output path must not contain symbolic links")
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii)
            # A TRAILING NEWLINE, because these files are read in diffs. The
            # registry emit used to append one and this function did not, so
            # routing the emit through here rewrote the last line of
            # six tracked documents with `\ No newline at end of file` — a
            # whole-file churn in the operator's diff for a byte nobody
            # intended to change. Every writer in the repository goes through
            # this function, so the convention belongs here.
            fh.write("\n")
            fh.flush()
            # The rename is atomic; the CONTENT reaching the platter is not
            # implied by it. On a machine that has already lost a database to a
            # write it could not finish, that distinction is the whole point.
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
        return dest
    except BaseException as exc:
        # Including KeyboardInterrupt and SystemExit: a half-written temp file
        # left in a scanned directory is litter the next run would glob.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        # A FULL DISK, NAMED. On 2026-09-07 at 06:39 the volume filled and four
        # collectors died here in the same tick, each with a five-frame
        # traceback ending in `[Errno 28] No space left on device` — so the tick
        # reported four failed steps and the log held four stack traces for ONE
        # cause. The failure is correct and stays; what was wrong was that the
        # cheapest fact to state was the hardest one to find. Raising it as a
        # sentence means every caller of this function inherits the sentence.
        if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            free = shutil.disk_usage(dest.parent).free
            raise OSError(
                errno.ENOSPC,
                f"no space left on the volume holding {dest} — {free // (1024*1024)} MiB "
                f"free. Nothing was written and the destination is intact; every "
                f"writer in this repository fails the same way until space is "
                f"freed.") from exc
        raise


def write_text(path: str | os.PathLike, text: str) -> pathlib.Path:
    """The same guarantee for text that `write_json` gives JSON.

    `Path.write_text` truncates the destination and only then begins writing —
    the exact sequence the module docstring describes. Several writers produce
    TRACKED files this way (the findings queue, the ledger export, generated
    docs), and a crash or a full disk between the two steps leaves a truncated
    file that the tick's registry commit would then COMMIT.

    Much of that output is not JSON — JSONL, markdown and HTML have no
    serialiser to hand the destination to — which is why this function exists
    rather than every caller being pointed at `write_json`.

    A trailing newline is NOT added here, unlike `write_json`. Its callers hand
    over text they have already composed — a rendered page, a stamped document,
    a JSONL body that ends where its last record does — and appending a byte to
    that would be whole-file diff churn.
    """
    dest = pathlib.Path(path)
    if any(p.is_symlink() for p in (dest, *dest.parents)):
        raise ValueError("Output path must not contain symbolic links")
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
        return dest
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json_carrying(path: str | os.PathLike, doc: dict, *,
                        stamps: tuple[str, ...], now: str, **kw) -> tuple[pathlib.Path, bool]:
    """Write `doc`, but keep the previous stamp when nothing else changed.

    Returns (path, changed).

    **A stamp that moves on every write says nothing about the data.** These
    files are rewritten by every tick and COMMITTED, so a fresh timestamp on
    identical content is a commit that records only that the clock advanced —
    and, worse, a reader cannot tell "measured again just now" from "changed
    just now". The fields named in `stamps` are therefore excluded from the
    comparison and carried forward when the rest of the document is unchanged.

    The opposite mistake is as bad: a hardcoded stamp makes every document
    claim a fixed age regardless of when it was measured, and the dashboard
    prints that claim as its freshness. One rule, in one place, for every
    stamped document.
    """
    dest = pathlib.Path(path)
    body = {k: v for k, v in doc.items() if k not in stamps}
    carried: dict[str, Any] = {}
    if dest.is_file():
        try:
            old = json.loads(dest.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            old = None
        if isinstance(old, dict):
            old_stamps = {k: old.pop(k, None) for k in stamps}
            if old == body:
                carried = {k: v for k, v in old_stamps.items() if v is not None}
    out = dict(doc)
    for k in stamps:
        out[k] = carried.get(k, now)
    # The key ORDER is preserved from `doc`, because these files are read by
    # people in a diff: a stamp that jumps to the end of the object on the run
    # that carries it forward would show as a move of every line between.
    write_json(dest, out, **kw)
    return dest, not carried
