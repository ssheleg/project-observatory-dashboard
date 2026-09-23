#!/usr/bin/env python3
"""Superseded. The one door to Cloudflare credentials is `tools/cloudflare.py`.

This name is kept so older instructions that point at it still land somewhere;
what it did (take a narrow token on stdin and file it) is now
`./tools/cloudflare.py install`, beside `stash`, `issue`, `rotate --leaked`,
`revoke` and `ping`. Two installers for one directory is how a token ends up
filed twice with different metadata, so this one only points at the other.
"""
import sys

print("this tool moved: use  ./tools/cloudflare.py  (stash | issue | install | "
      "list | ping | rotate | revoke)", file=sys.stderr)
sys.exit(2)
