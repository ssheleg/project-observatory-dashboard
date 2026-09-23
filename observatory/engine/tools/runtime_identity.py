#!/usr/bin/env python3
""                                                                            

                                                                                
                                                                            
                                                                               
                                                                           
   
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths
from runtime_identity import IdentityError, KINDS, load


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('init', 'inspect'))
    ap.add_argument('kind', choices=tuple(KINDS))
    args = ap.parse_args(argv)
    path = paths.STATE / KINDS[args.kind][0]
    try:
        load(path, args.kind, initialize=args.action == 'init')
    except IdentityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f'{args.kind}: ready at {path}; value not displayed. Workspace activation is separate.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
