#!/usr/bin/env python3
"""Runtime identity checks use disposable roots and never report values."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
FAILURES = []
PASSES = 0
KINDS = {'keyserver-token': ('tools.keyserver', 'token', '.keyserver-token', 'T' * 43),
         'env-fingerprint-salt': ('collectors.scan_env', 'salt', '.env-fingerprint-salt', 'a' * 64)}


def check(name, ok):
    global PASSES
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
    if ok:
        PASSES += 1
    else:
        FAILURES.append(name)


def env(root):
    return {**os.environ, 'OBSERVATORY_STATE': str(root / 'state'),
            'OBSERVATORY_SCRATCH': str(root / 'raw'),
            'OBSERVATORY_REGISTRY': str(root / 'registry'),
            'OBSERVATORY_DATA': str(root / 'data')}


def put(path, value, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value)
    path.chmod(mode)


def reader(root, kind, default=False):
    module, fn, _, _ = KINDS[kind]
    # Old implementations can only touch this synthetic legacy sentinel.
    code = f'''import paths, pathlib, importlib, json, hashlib
paths.STORE = pathlib.Path({str(root / 'legacy')!r})
if {default!r}: paths.STATE = paths.STORE
m = importlib.import_module({module!r})
try:
    value = getattr(m, {fn!r})()
    print(json.dumps({{"ok": True, "digest": hashlib.sha256(value.encode()).hexdigest()}}))
except BaseException as exc:
    print(json.dumps({{"ok": False, "error": str(exc)}}))
'''
    p = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env(root),
                       capture_output=True, text=True, timeout=15)
    if p.returncode:
        raise RuntimeError('reader subprocess failed without a structured response')
    return json.loads(p.stdout)


def cli(root, kind, action='init'):
    return subprocess.run([sys.executable, str(ROOT / 'tools/runtime_identity.py'), action, kind],
                          cwd=ROOT, env=env(root), capture_output=True, text=True, timeout=15)


def program(root, script, *args):
    # Even a regression to STORE must only read/write a synthetic checkout.
    code = f"import paths, pathlib, runpy, sys; paths.STORE = pathlib.Path({str(root / 'legacy')!r}); sys.argv = {[script, *args]!r}; runpy.run_path({str(ROOT)!r} + '/' + {script!r}, run_name='__main__')"
    return [sys.executable, '-c', code]


def test_existing_and_isolated():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for kind, (_, _, name, value) in KINDS.items():
            a, b = base / (kind + '-a'), base / (kind + '-b')
            put(a / 'legacy' / name, value + '\n')
            legacy = reader(a, kind, default=True)
            check(kind + ' default compatibility', legacy.get('digest') == hashlib.sha256(value.encode()).hexdigest())
            check(kind + ' default bytes unchanged', (a / 'legacy' / name).read_text() == value + '\n')
            missing = reader(a, kind)
            check(kind + ' no source fallback', not missing['ok'])
            check(kind + ' reads never initialize', not (a / 'state' / name).exists())
            check(kind + ' absent default also refuses', not reader(b, kind, default=True)['ok'] and not (b / 'legacy' / name).exists())
            first, second = cli(a, kind), cli(b, kind)
            check(kind + ' explicit init works', first.returncode == second.returncode == 0)
            if first.returncode or second.returncode:
                continue
            original = (a / 'state' / name).read_bytes()
            one, two = reader(a, kind), reader(b, kind)
            check(kind + ' independent roots', one['ok'] and two['ok'] and one['digest'] != two['digest'])
            check(kind + ' repeat read stable', reader(a, kind) == one)
            check(kind + ' init idempotent', cli(a, kind).returncode == 0 and (a / 'state' / name).read_bytes() == original)
            check(kind + ' private modes', (a / 'state').stat().st_mode & 0o777 == 0o700 and (a / 'state' / name).stat().st_mode & 0o777 == 0o600)
            check(kind + ' CLI never displays value', original.strip().decode() not in first.stdout + first.stderr)
            check(kind + ' legacy untouched', (a / 'legacy' / name).read_text() == value + '\n')
            (a / 'state' / name).unlink()
            check(kind + ' loss refuses restart', not reader(a, kind)['ok'] and not (a / 'state' / name).exists())


def test_bad_state_is_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        for kind, (_, _, name, value) in KINDS.items():
            for label, content, mode in [('empty', '', 0o600), ('malformed', 'PRIVATE-BAD-CONTENT', 0o600),
                                         ('oversized', 'x' * 8192, 0o600), ('loose', value, 0o640),
                                         ('two-lines', value + '\n' + value, 0o600)]:
                root = Path(tmp) / kind / label
                path = root / 'state' / name
                put(path, content, mode)
                put(root / 'legacy' / name, value)
                result, run = reader(root, kind), cli(root, kind)
                check(kind + ' refuses ' + label, not result['ok'] and run.returncode == 2)
                check(kind + ' preserves ' + label, path.read_text() == content and path.stat().st_mode & 0o777 == mode)
                check(kind + ' safe recovery message ' + label,
                      'restore' in (result.get('error', '') + run.stderr).lower() and
                      (not content or content not in run.stdout + run.stderr + result.get('error', '')))
            for label in ('symlink', 'directory', 'fifo', 'parent-symlink', 'parent-writable', 'parent-file'):
                root = Path(tmp) / kind / label
                state = root / 'state'; root.mkdir(parents=True)
                outside = root / 'outside'; put(outside / name, value)
                if label == 'parent-symlink':
                    state.symlink_to(outside, target_is_directory=True)
                elif label == 'parent-file':
                    state.write_text('keep')
                else:
                    state.mkdir(mode=0o700)
                    if label == 'symlink': (state / name).symlink_to(outside / name)
                    elif label == 'directory': (state / name).mkdir()
                    elif label == 'fifo': os.mkfifo(state / name, 0o600)
                    else:
                        put(state / name, value); state.chmod(0o777)
                result, run = reader(root, kind), cli(root, kind)
                check(kind + ' refuses unsafe ' + label, not result['ok'] and run.returncode == 2)
                check(kind + ' external bytes unchanged ' + label, (outside / name).read_text() == value)


def test_parallel_initializers():
    with tempfile.TemporaryDirectory() as tmp:
        for kind, (_, _, name, _) in KINDS.items():
            root = Path(tmp) / kind
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: cli(root, kind), range(8)))
            check(kind + ' concurrent init succeeds', all(r.returncode == 0 for r in results))
            if any(r.returncode for r in results): continue
            digest = reader(root, kind)
            check(kind + ' concurrent init converges', all(reader(root, kind) == digest for _ in range(4)))
            check(kind + ' no publication residue', sorted(p.name for p in (root / 'state').iterdir()) == [name])


def test_failed_publication_and_unreadable_state():
    sys.path.insert(0, str(ROOT))
    import runtime_identity as identity
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for kind, (_, _, name, value) in KINDS.items():
            path = root / kind / name
            for operation in ('fsync', 'link'):
                with patch.object(identity.os, operation, side_effect=OSError('injected private error')):
                    try:
                        identity.load(path, kind, initialize=True)
                        refused = False
                    except identity.IdentityError as exc:
                        refused = 'injected private error' not in str(exc)
                check(kind + ' failed ' + operation + ' leaves no identity', refused and not path.exists())
                check(kind + ' failed ' + operation + ' cleans temporary file', not list(path.parent.iterdir()))
            candidate = path.parent / ('.identity-' + 'c' * 32 + '.tmp')
            candidate.write_text('another initializer owns this')
            with patch.object(identity.secrets, 'token_hex', return_value='c' * 32):
                try:
                    identity.load(path, kind, initialize=True)
                    refused = False
                except identity.IdentityError:
                    refused = True
            check(kind + ' colliding temporary file preserved', refused and candidate.read_text() == 'another initializer owns this' and not path.exists())
            candidate.unlink()
            put(path, value)
            with patch.object(identity.os, 'open', side_effect=PermissionError('injected private error')):
                try:
                    identity.load(path, kind, initialize=True)
                    refused = False
                except identity.IdentityError as exc:
                    refused = 'injected private error' not in str(exc)
            check(kind + ' inaccessible state preserved', refused and path.read_text() == value)
            path.write_bytes(b'\xff' * 64)
            try:
                identity.load(path, kind, initialize=True)
                refused = False
            except identity.IdentityError:
                refused = True
            check(kind + ' non-ASCII bytes preserved', refused and path.read_bytes() == b'\xff' * 64)


def test_remote_scanner_refuses_before_provider():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); output = root / 'remote.json'
        output.write_text('{"previous":true}\n')
        code = f'''import paths, pathlib, json
import configuration
configuration.enabled = lambda *args, **kwargs: True
paths.STORE = pathlib.Path({str(root / 'legacy')!r})
from collectors import scan_remote_env as remote
def forbidden(*args, **kwargs):
    raise AssertionError('provider must not be reached')
remote.scan_heroku_apps = forbidden
status = remote.main(['scan_remote_env.py', {str(output)!r}, '--force'])
print(json.dumps({{"status": status}}))
'''
        p = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env(root),
                           capture_output=True, text=True, timeout=15)
        check('remote scanner refuses before provider with safe diagnostic',
              p.returncode == 0 and json.loads(p.stdout)['status'] == 1 and 'Restore' in p.stderr)
        check('remote scanner preserves previous inventory', output.read_text() == '{"previous":true}\n')


def test_scanner_and_server_fail_before_effects():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); (root / 'data' / 'project').mkdir(parents=True)
        # Synthetic value never leaves the scanner except through a fingerprint.
        (root / 'data' / 'project' / '.env').write_text('API_TOKEN=' + '7d41f0bc9a2e5183c6b740fe29ad5c83' + '\n')
        output = root / 'inventory.json'; output.write_text('{"previous":true}\n')
        cmd = program(root, 'collectors/scan_env.py', str(output))
        p = subprocess.run(cmd, cwd=ROOT, env=env(root), capture_output=True, text=True, timeout=15)
        check('missing salt preserves previous scan', p.returncode == 2 and output.read_text() == '{"previous":true}\n')
        p = subprocess.run(program(root, 'tools/keyserver.py', '--host', '127.0.0.1', '--port', '-1', '--once'),
                           cwd=ROOT, env=env(root), capture_output=True, text=True, timeout=15)
        check('missing token prevents server startup', p.returncode == 2 and 'keyserver on' not in p.stdout)
        r = cli(root, 'env-fingerprint-salt')
        if r.returncode:
            check('scanner salt init', False); return
        runs = [subprocess.run(cmd, cwd=ROOT, env=env(root), capture_output=True, text=True, timeout=15) for _ in range(2)]
        first = json.loads(output.read_text())
        check('scanner with initialized salt works', all(p.returncode == 0 for p in runs) and bool(first.get('files')))
        if not first.get('files'): return
        fp = first['files'][0]['variables'][0]['fingerprint']
        subprocess.run(cmd, cwd=ROOT, env=env(root), capture_output=True, timeout=15, check=True)
        check('scanner fingerprint stable', json.loads(output.read_text())['files'][0]['variables'][0]['fingerprint'] == fp)
        other = root / 'other'; cli(other, 'env-fingerprint-salt')
        e = env(root); e['OBSERVATORY_STATE'] = str(other / 'state')
        subprocess.run(cmd, cwd=ROOT, env=e, capture_output=True, timeout=15, check=True)
        check('scanner fingerprint scope isolated', json.loads(output.read_text())['files'][0]['variables'][0]['fingerprint'] != fp)
        put(root / 'state' / '.env-fingerprint-salt', 'broken')
        before = output.read_bytes()
        p = subprocess.run(cmd, cwd=ROOT, env=env(root), capture_output=True, timeout=15)
        check('corrupt salt preserves previous scan', p.returncode == 2 and output.read_bytes() == before)


if __name__ == '__main__':
    for fn in (test_existing_and_isolated, test_bad_state_is_preserved,
               test_parallel_initializers, test_failed_publication_and_unreadable_state,
               test_remote_scanner_refuses_before_provider, test_scanner_and_server_fail_before_effects):
        fn()
    print(f'{PASSES} PASS; {len(FAILURES)} FAIL')
    raise SystemExit(bool(FAILURES))
