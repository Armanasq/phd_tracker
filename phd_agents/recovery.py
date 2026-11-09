from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from .store import ConflictError, default_path

_BACKUP_NAME = re.compile(
    r"phd-atlas-(?:\d{8}T\d{6}Z-[0-9a-f]{10}|pre-restore-\d{8}T\d{6}Z-[0-9a-f]{10})\.sqlite3"
)
_REQUIRED_TABLES = frozenset({
    "catalog", "applications", "runs", "audit", "schedule",
    "private_objects", "conversations", "conversation_messages",
})


@contextmanager
def runtime_lock(state_path: Path) -> Iterator[None]:
    if os.name != "posix":
        yield
        return
    import fcntl

    state_path = Path(state_path).expanduser()
    parent = state_path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if parent.is_symlink():
        raise PermissionError("Private state directory cannot be a symlink")
    filename = parent / ("." + state_path.name + ".runtime.lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(filename, flags, 0o600)
    try:
        if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o077:
            raise PermissionError("Private runtime lock must be owner-only")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ConflictError("Private runtime is active; stop it before restoring state") from error
        yield
    finally:
        os.close(descriptor)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_database(path: Path) -> None:
    try:
        uri = "file:" + quote(str(path.absolute())) + "?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=5) as database:
            if database.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok":
                raise ValueError("Backup failed the SQLite integrity check")
            if database.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Backup contains foreign-key violations")
            names = {
                item[0] for item in database.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not _REQUIRED_TABLES.issubset(names):
                raise ValueError("Backup does not contain the expected private workspace schema")
    except sqlite3.DatabaseError as error:
        raise ValueError("Backup is not a readable SQLite workspace database") from error


def verify_backup(
    name: str, *, state_path: Path | None = None, sha256: str | None = None,
) -> dict[str, object]:
    if not isinstance(name, str) or not _BACKUP_NAME.fullmatch(name):
        raise ValueError("Backup must be an existing generated filename, not a path")
    if sha256 is not None and (
        not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256)
    ):
        raise ValueError("Expected SHA-256 must be 64 lowercase hexadecimal characters")
    state = Path(state_path) if state_path is not None else default_path()
    directory = state.expanduser().parent / "backups"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Private backup directory is missing or unsafe")
    if stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise PermissionError("Backup directory must be owner-only")
    candidate = directory / name
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("Backup file does not exist or is not an ordinary file")
    if stat.S_IMODE(candidate.stat().st_mode) & 0o077:
        raise PermissionError("Backup file must be owner-only")
    if hasattr(os, "getuid") and candidate.stat().st_uid != os.getuid():
        raise PermissionError("Backup file is not owned by the current user")
    _verify_database(candidate)
    digest = _file_digest(candidate)
    if sha256 is not None and digest != sha256:
        raise ValueError("Backup SHA-256 does not match the expected digest")
    return {
        "filename": name,
        "size_bytes": candidate.stat().st_size,
        "sha256": digest,
        "integrity": "ok",
        "credentials_included": False,
    }


def _copy_private(source: Path, target: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as dest, source.open("rb") as stream:
            shutil.copyfileobj(stream, dest, 1024 * 1024)
            dest.flush()
            os.fsync(dest.fileno())
    except BaseException:
        if target.exists():
            target.unlink()
        raise


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def restore_backup(
    name: str, *, state_path: Path | None = None, sha256: str | None = None,
    confirm: bool = False,
) -> dict[str, object]:
    if confirm is not True:
        raise PermissionError("Restore requires explicit --confirm and a stopped runtime")
    if os.name != "posix":
        raise RuntimeError("Automated offline restore currently requires POSIX file locks")
    state = (Path(state_path) if state_path is not None else default_path()).expanduser()
    with runtime_lock(state):
        inspected = verify_backup(name, state_path=state, sha256=sha256)
        if state.is_symlink() or (state.exists() and not state.is_file()):
            raise PermissionError("Private state must be an ordinary file")
        if state.is_file() and stat.S_IMODE(state.stat().st_mode) & 0o077:
            raise PermissionError("Current private state has unsafe file permissions")
        if any(Path(str(state) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise ConflictError("SQLite journal sidecars exist; stop and cleanly checkpoint the runtime first")
        source = state.parent / "backups" / name
        descriptor, staged_name = tempfile.mkstemp(prefix=".phd-restore-", suffix=".tmp", dir=state.parent)
        os.close(descriptor)
        staged = Path(staged_name)
        preserved: Path | None = None
        try:
            with source.open("rb") as stream, staged.open("wb") as destination:
                shutil.copyfileobj(stream, destination, 1024 * 1024)
                destination.flush()
                os.fsync(destination.fileno())
            os.chmod(staged, 0o600)
            _verify_database(staged)
            if state.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                preserved = source.parent / (
                    "phd-atlas-pre-restore-" + stamp + "-" + uuid.uuid4().hex[:10] + ".sqlite3"
                )
                _copy_private(state, preserved)
                _sync_directory(source.parent)
            os.replace(staged, state)
            _sync_directory(state.parent)
        finally:
            if staged.exists():
                staged.unlink()
        return {
            "restored": True,
            "source": name,
            "sha256": inspected["sha256"],
            "previous_state": preserved.name if preserved is not None else None,
            "credentials_restored": False,
            "restart_required": True,
        }
