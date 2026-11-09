from __future__ import annotations
import json
import os
import re
import tempfile
from pathlib import Path
from .store import default_path

_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")

def secret_path() -> Path:
    return default_path().parent / "provider-credentials.json"

def read_secret(name: str) -> str:
    if not _NAME.fullmatch(name):
        return ""
    value = os.environ.get(name)
    if value:
        return value
    path = secret_path()
    if not path.is_file():
        return ""
    if path.stat().st_mode & 0o077:
        raise PermissionError("Provider credential file has unsafe permissions")
    return str(json.loads(path.read_text(encoding="utf-8")).get(name) or "")

def write_secret(name: str, value: str) -> None:
    if not _NAME.fullmatch(name):
        raise ValueError("Invalid credential variable name")
    if not isinstance(value, str) or len(value) > 8192:
        raise ValueError("Invalid credential value")
    path = secret_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_mode & 0o077:
        raise PermissionError("Provider credential file has unsafe permissions")
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if value:
        data[name] = value
    else:
        data.pop(name, None)
    fd, temp = tempfile.mkstemp(prefix=".provider-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
