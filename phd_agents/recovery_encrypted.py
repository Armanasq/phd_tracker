from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .recovery import (
    _copy_private, _sync_directory, _verify_database,
    restore_backup, verify_backup,
)
from .store import default_path

_MAGIC = b"PHDAIENC1"
_SALT_SIZE = 16
_NONCE_SIZE = 12
_TAG_SIZE = 16
_HEADER_SIZE = len(_MAGIC) + _SALT_SIZE + _NONCE_SIZE
_BLOCK = 1_048_576


def _crypto():
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError as error:
        raise RuntimeError("Encrypted backup requires pip install -r requirements-recovery.txt") from error
    return InvalidTag, Cipher, algorithms, modes, Scrypt


def _key(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or not 16 <= len(passphrase) <= 1024:
        raise ValueError("Use a high-entropy backup passphrase of at least 16 characters")
    _, _, _, _, Scrypt = _crypto()
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(passphrase.encode("utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_BLOCK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_encrypted_backup(
    filename: str, output_path: Path, passphrase: str, *,
    state_path: Path | None = None,
    sha256: str | None = None, repo_root: Path | None = None,
) -> dict[str, object]:
    if os.name != "posix":
        raise RuntimeError("Encrypted backup export requires POSIX owner-only permissions")
    state = (Path(state_path) if state_path is not None else default_path()).expanduser()
    report = verify_backup(filename, state_path=state, sha256=sha256)
    destination = Path(output_path).expanduser()
    repository = (Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]).resolve()
    if destination.resolve().is_relative_to(repository):
        raise PermissionError("Encrypted backup must be written outside the Git repository")
    if destination.is_symlink() or destination.exists() or not destination.parent.is_dir():
        raise ValueError("Encrypted backup destination must be a new ordinary file in an existing directory")
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    header = _MAGIC + salt + nonce
    key = _key(passphrase, salt)
    _, Cipher, algorithms, modes, _ = _crypto()
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    source_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(state.parent / "backups" / filename, source_flags), "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError("Backup source must remain an owner-only ordinary file")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise PermissionError("Backup source owner changed after verification")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        try:
            observed_digest = hashlib.sha256()
            observed_size = 0
            with os.fdopen(descriptor, "wb") as output:
                output.write(header)
                for chunk in iter(lambda: source.read(_BLOCK), b""):
                    observed_digest.update(chunk)
                    observed_size += len(chunk)
                    output.write(encryptor.update(chunk))
                if observed_size != report["size_bytes"] or observed_digest.hexdigest() != report["sha256"]:
                    raise ValueError("Backup contents changed between verification and encrypted export")
                output.write(encryptor.finalize())
                output.write(encryptor.tag)
                output.flush()
                os.fsync(output.fileno())
            if stat.S_IMODE(destination.stat().st_mode) != 0o600:
                raise PermissionError("Encrypted backup must be owner-only")
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return {
        "encrypted": True,
        "path": str(destination),
        "format": "PHDAIENC1_scrypt_aes256gcm",
        "private_file_mode": "0o600",
        "plaintext_sha256": report["sha256"],
        "plaintext_size_bytes": report["size_bytes"],
        "provider_credentials_included": False,
        "off_host_copy_completed": False,
    }


def _decrypt_authenticated_backup(
    encrypted_path: Path, passphrase: str, *, sha256: str, destination: Path,
) -> None:
    if os.name != "posix":
        raise RuntimeError("Encrypted recovery requires POSIX owner-only temporary files")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("An independently recorded SHA-256 digest is required")
    encrypted = Path(encrypted_path).expanduser()
    if encrypted.is_symlink() or not encrypted.is_file():
        raise ValueError("Encrypted backup is missing or unsafe")
    InvalidTag, Cipher, algorithms, modes, _ = _crypto()
    source_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(encrypted, source_flags), "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= _HEADER_SIZE + _TAG_SIZE:
            raise ValueError("Encrypted backup is malformed")
        header = source.read(_HEADER_SIZE)
        if len(header) != _HEADER_SIZE or not header.startswith(_MAGIC):
            raise ValueError("Unsupported encrypted backup format")
        salt = header[len(_MAGIC):len(_MAGIC) + _SALT_SIZE]
        nonce = header[-_NONCE_SIZE:]
        key = _key(passphrase, salt)
        source.seek(-_TAG_SIZE, os.SEEK_END)
        tag = source.read(_TAG_SIZE)
        source.seek(_HEADER_SIZE)
        remaining = metadata.st_size - _HEADER_SIZE - _TAG_SIZE
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(header)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as plaintext:
                while remaining:
                    chunk = source.read(min(_BLOCK, remaining))
                    if not chunk:
                        raise ValueError("Encrypted backup ended prematurely")
                    remaining -= len(chunk)
                    plaintext.write(decryptor.update(chunk))
                plaintext.write(decryptor.finalize())
                plaintext.flush()
                os.fsync(plaintext.fileno())
        except InvalidTag as error:
            raise ValueError("Encrypted backup authentication failed") from error
    if stat.S_IMODE(destination.stat().st_mode) != 0o600:
        raise PermissionError("Recovered data was not stored with owner-only permissions")
    if _sha256(destination) != sha256:
        raise ValueError("Decrypted backup does not match the independently recorded SHA-256")
    _verify_database(destination)


def drill_encrypted_backup(
    encrypted_path: Path, passphrase: str, *, sha256: str,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="phd-encrypted-drill-") as folder:
        _decrypt_authenticated_backup(
            encrypted_path, passphrase, sha256=sha256,
            destination=Path(folder) / "recovered.sqlite3",
        )
        return {
            "drill": "passed",
            "format": "PHDAIENC1_scrypt_aes256gcm",
            "sha256": sha256,
            "private_file_mode": "0o600",
            "sqlite_integrity": "ok",
            "restored_in_isolation": True,
            "live_state_writes_performed": False,
            "off_host_copy_verified": False,
            "provider_credentials_restored": False,
        }


def restore_encrypted_backup(
    encrypted_path: Path, passphrase: str, *, sha256: str,
    state_path: Path | None = None, confirm: bool = False,
) -> dict[str, object]:
    if confirm is not True:
        raise PermissionError("Encrypted restore requires explicit --confirm and a stopped runtime")
    if os.name != "posix":
        raise RuntimeError("Encrypted state restore requires POSIX owner-only locks and permissions")
    state = (Path(state_path) if state_path is not None else default_path()).expanduser()
    parent = state.parent
    if parent.is_symlink():
        raise PermissionError("Private state directory cannot be a symlink")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise PermissionError("Private state directory must be owner-only")
    if hasattr(os, "getuid") and parent.stat().st_uid != os.getuid():
        raise PermissionError("Private state directory must be owned by the current user")
    backups = parent / "backups"
    if backups.is_symlink():
        raise PermissionError("Private backup directory cannot be a symlink")
    backups.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(backups.stat().st_mode) & 0o077:
        raise PermissionError("Private backup directory must be owner-only")
    if hasattr(os, "getuid") and backups.stat().st_uid != os.getuid():
        raise PermissionError("Private backup directory must be owned by the current user")
    with tempfile.TemporaryDirectory(prefix=".phd-encrypted-restore-", dir=parent) as folder:
        recovered = Path(folder) / "recovered.sqlite3"
        _decrypt_authenticated_backup(
            encrypted_path, passphrase, sha256=sha256, destination=recovered,
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = "phd-atlas-" + stamp + "-" + uuid.uuid4().hex[:10] + ".sqlite3"
        staged_backup = backups / filename
        _copy_private(recovered, staged_backup)
        _sync_directory(backups)
        try:
            result = restore_backup(
                filename, state_path=state, sha256=sha256, confirm=True,
            )
        finally:
            staged_backup.unlink(missing_ok=True)
            _sync_directory(backups)
    return {
        **result,
        "encrypted_source": True,
        "format": "PHDAIENC1_scrypt_aes256gcm",
        "off_host_copy_verified": False,
        "provider_credentials_restored": False,
    }
