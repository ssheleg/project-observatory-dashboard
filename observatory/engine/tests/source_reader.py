#!/usr/bin/env python3
"""Read Python source as CODE, with comments and docstrings removed.

Five assertions in one sitting broke on one shape: *"this string must not appear
in the source"*. It is wrong by construction, because a fix documents what it
removed — so the prose explaining the removal satisfies the pattern the
assertion forbids.

The five, in order:

1. `tools/check_docs.py` — a retired claim quoted inside its own retirement
2. `tests/test_corroboration.py` — `NO_MECHANICAL_CHECK`, whose words survived in
   the comment explaining its deletion
3. `tests/test_tick.py` — an ordering assertion using `src.find`, broken by a
   comment naming the script
4. `tests/test_corroboration.py` again — the same comparison, the same comment
5. `tests/test_notification.py` — `abs(hash(ref))`, named in the comment saying
   why it is gone

Numbers 3 and 4 produced `tests/tick_reader.py`, for shell. This is the Python
half: `code_only()` strips comments and string literals, so "the pattern is gone
from the code" can be asserted without forbidding the sentence that explains it.

Strings go too, not only comments. A docstring is a string literal, and so is
the message in `raise ValueError("abs(hash(ref)) was removed")` — both are prose
about the code rather than the code itself.
"""
from __future__ import annotations
import io
import tokenize


def code_only(src: str) -> str:
    """The source with comments and string literals blanked out, IN PLACE.

    Blanked rather than deleted, so line and column numbers line up with the
    original and a substring search still means what it looks like.

    The first version collected the surviving tokens and joined them with
    newlines, which contradicted this docstring and broke every caller: `def
    report(` became three lines, so `"def report(" in code_only(src)` was False
    for a file that plainly contains it. Four assertions failed on that within a
    minute of the module being written — the docstring promising what the code
    did not do, in the module built to stop assertions matching prose.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # A file that does not tokenize is a different problem, and silently
        # returning the raw source would let a prose match through unnoticed.
        raise
    lines = src.splitlines(keepends=True)
    grid = [list(l) for l in lines]
    prose_tokens = {tokenize.COMMENT, tokenize.STRING}
                                                                       
                                                
    prose_tokens.update(getattr(tokenize, name) for name in
                        ('FSTRING_START', 'FSTRING_MIDDLE', 'FSTRING_END')
                        if hasattr(tokenize, name))
    for tok in tokens:
        if tok.type not in prose_tokens:
            continue
        (r1, c1), (r2, c2) = tok.start, tok.end
        for row in range(r1 - 1, min(r2, len(grid))):
            line = grid[row]
            start = c1 if row == r1 - 1 else 0
            end = c2 if row == r2 - 1 else len(line)
            for col in range(start, min(end, len(line))):
                if line[col] != "\n":
                    line[col] = " "
    return "".join("".join(l) for l in grid)


def appears_in_code(src: str, needle: str) -> bool:
    """True when `needle` is in the code rather than only in its documentation."""
    return needle in code_only(src)


def code_lines(src: str, needle: str) -> list[int]:
    ""                                                                         
    hits = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        if needle in tok.line and tok.start[0] not in hits:
            # The token's own line, minus the possibility that the match sits in
            # a trailing comment on it: re-check the line with comments stripped.
            bare = tok.line.split("#", 1)[0]
            if needle in bare:
                hits.append(tok.start[0])
    return hits


def code_keeping_strings(src: str) -> str:
    """Prose removed, string literals KEPT, embedded `//` comments removed too.

    A third reader, because the two above answer different questions and neither
    fits the class "a core file must not name a plugin's vocabulary":

                                                                  
                                                                       
                                                                              
                                                                     
                                                                             
                                                                               
                                                                         
                                                                        
                                                  

    So: keep the strings, and treat a line that is a comment in the EMBEDDED
    language as prose as well. Deleting a comment to satisfy a checker is the
    trade this repository has refused twice already (`dashboard/audit_pack.py`
    strips CSS comments for the same reason); teaching the reader is cheaper
    than losing the explanation.
    """
    import re
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import check_paths
    return re.sub(r"^\s*//.*$", "", check_paths.prose_removed(src), flags=re.M)
