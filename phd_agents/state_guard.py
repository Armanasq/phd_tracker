from __future__ import annotations

import os
import stat
from pathlib import Path


class StateLockBusy(RuntimeError):
    pass


def acquire_state_guard(path: Path, *, exclusive: bool) -> int | None:
    if os.name != "posix":
        if exclusive:
            raise RuntimeError("Exclusive SQLite state restoration requires POSIX advisory locks")
        return None

    import fcntl

    target = Path(path).expanduser()
    directory = target.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise PermissionError("Private state directory cannot be a symlink")

    filename = directory / ("." + target.name + ".database.lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(filename, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError("Private database coordination lock must be an owner-only file")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise PermissionError("Private database coordination lock is not owned by this user")
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StateLockBusy("Private SQLite state is in use by an incompatible operation") from error
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def release_state_guard(descriptor: int | None) -> None:
    if descriptor is not None:
        os.close(descriptor)
