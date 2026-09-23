#!/usr/bin/env python3
"""The rule two remote listings both need: an empty success is not a measurement.

`gh repo list` exits 0 with `[]` when the token has lost access to an
organisation. Bitbucket answers HTTP 200 with no `values` when the credential
can no longer see a private workspace — its own docstring records that the 200
"is not access". In both cases the transport succeeded, so nothing downstream
has any reason to doubt the answer, and the repositories simply stop existing.

                                                                           
                                                                      
                                                                           
                                                                             
                                                                                 
               

                                                                                
                                                                               
                                                                             
                                                                             
                                                                            
                                          

What it deliberately does NOT do: refuse an empty listing when there was nothing
to lose. An owner or workspace with genuinely no repositories is a fact, and
recording it is the collector's job.
"""
from __future__ import annotations


def plural(n: int) -> str:
    return "repository" if n == 1 else "repositories"


def empty_would_lose(label: str, previous_count: int, new_count: int,
                     remedy: str) -> str | None:
    """The reason to record, or None when the empty answer costs nothing.

    `label` names the surface as `degraded` will name it — `github:ssheleg`,
    `bitbucket:mobyrix` — so a host reading the list can tell WHICH surface went
    dark rather than merely that something did. `remedy` is the caller's own
    sentence about how a human forces the empty answer through, because only the
    caller knows what it keeps and where.
    """
    if new_count or previous_count <= 0:
        return None
    return (f"the listing for {label} succeeded and returned NOTHING while the "
            f"previous one held {previous_count} {plural(previous_count)}. "
            f"Keeping the previous answer: a credential that lost access to an "
            f"organisation looks exactly like this from here, and an answer that "
            f"is older is worth more than one that is wrong. {remedy}")
