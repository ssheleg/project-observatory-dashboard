#!/usr/bin/env python3
""                                                       
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import dashboard_fixture


def test_env_page():
    with tempfile.TemporaryDirectory(prefix='observatory-env-page-') as td:
        page=dashboard_fixture.build(Path(td))
        result=subprocess.run(['node',str(ROOT/'tests/env_tab_check.js'),str(page)],cwd=ROOT)
        if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':
    test_env_page()
