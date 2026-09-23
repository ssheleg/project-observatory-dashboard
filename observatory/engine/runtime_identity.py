"""Private runtime identity: reads never bootstrap; init never replaces.

The selected final directory is opened without following a symlink. Operations
are relative to that descriptor. Ancestors belong to the local operator; this
is not a defence against a hostile owner moving the ancestor hierarchy.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import secrets
import stat

KINDS = {
    'keyserver-token': ('.keyserver-token', r'[A-Za-z0-9_-]{43}', lambda: secrets.token_urlsafe(32)),
    'env-fingerprint-salt': ('.env-fingerprint-salt', r'[0-9a-f]{64}', lambda: secrets.token_hex(32)),
}
MAX_BYTES = 128


class IdentityError(RuntimeError):
    """Safe diagnostic containing a path and reason, never file contents."""


def failure(path: Path, kind: str, reason: str) -> IdentityError:
    return IdentityError(
        f'{kind}: {reason}: {path}. Restore a known good copy to preserve identity. '
        f'Only for a new identity, run `project-observatory full init` (or '
        f'`python3 tools/runtime_identity.py init {kind}`) with the same '
        'OBSERVATORY_STATE. Existing files are never replaced.')


def _directory(path: Path, kind: str, initialize: bool) -> int:
    if initialize:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022:
            raise failure(path, kind, 'state directory owner or permissions are unsafe')
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read(fd: int, path: Path, kind: str) -> str:
    # NONBLOCK makes a FIFO refuse without waiting for a writer.
    child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        info = os.fstat(child)
        if not stat.S_ISREG(info.st_mode):
            raise failure(path, kind, 'identity is not a regular file')
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise failure(path, kind, 'identity owner or permissions are unsafe; require owner-only access')
        with os.fdopen(child, 'rb', closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        try:
            value = data.decode('ascii').strip()
        except UnicodeError:
            value = ''
        if len(data) > MAX_BYTES or not re.fullmatch(KINDS[kind][1], value):
            raise failure(path, kind, 'identity is empty or invalid')
        return value
    finally:
        os.close(child)


def load(path: Path, kind: str, *, initialize: bool = False) -> str:
    """Read one identity, or explicitly publish a fully written new file.

    link() is atomic and refuses an existing destination. Another initializer
    either wins publication or reads the same complete winner. No O_TRUNC path.
    Errors leave any existing destination untouched; no legacy fallback exists.
    """
    if kind not in KINDS:
        raise ValueError('unknown runtime identity kind')
    fd = None
    temporary = None
    try:
        fd = _directory(path, kind, initialize)
        try:
            return _read(fd, path, kind)
        except FileNotFoundError:
            if not initialize:
                raise
        candidate = f'.identity-{secrets.token_hex(16)}.tmp'
        child = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600, dir_fd=fd)
        temporary = candidate  # cleanup only a file this call actually created
        with os.fdopen(child, 'wb') as stream:
            stream.write((KINDS[kind][2]() + '\n').encode('ascii'))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd,
                    follow_symlinks=False)
        except FileExistsError:
            pass
        os.fsync(fd)
        return _read(fd, path, kind)
    except FileNotFoundError:
        raise failure(path, kind, 'identity is missing; no new value was created') from None
    except OSError:
        raise failure(path, kind, 'state cannot be read or initialized; check path and permissions') from None
    finally:
        if fd is not None:
            try:
                if temporary is not None:
                    try:
                        os.unlink(temporary, dir_fd=fd)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        raise failure(path, kind, 'temporary file cleanup failed; inspect private state') from None
            finally:
                os.close(fd)
