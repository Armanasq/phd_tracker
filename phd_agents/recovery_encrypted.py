from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path

from .recovery import _verify_database, verify_backup
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
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output, (state.parent / "backups" / filename).open("rb") as source:
            output.write(header)
            for chunk in iter(lambda: source.read(_BLOCK), b""):
                output.write(encryptor.update(chunk))
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


def drill_encrypted_backup(
    encrypted_path: Path, passphrase: str, *, sha256: str,
) -> dict[str, object]:
    if os.name != "posix":
        raise RuntimeError("Encrypted restore drills require POSIX owner-only temporary files")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("An independently recorded SHA-256 digest is required")
    encrypted = Path(encrypted_path).expanduser()
    if encrypted.is_symlink() or not encrypted.is_file() or encrypted.stat().st_size <= _HEADER_SIZE + _TAG_SIZE:
        raise ValueError("Encrypted backup is missing or malformed")
    InvalidTag, Cipher, algorithms, modes, _ = _crypto()
    with encrypted.open("rb") as source:
        header = source.read(_HEADER_SIZE)
        if len(header) != _HEADER_SIZE or not header.startswith(_MAGIC):
            raise ValueError("Unsupported encrypted backup format")
        salt = header[len(_MAGIC):len(_MAGIC) + _SALT_SIZE]
        nonce = header[-_NONCE_SIZE:]
        key = _key(passphrase, salt)
        source.seek(-_TAG_SIZE, os.SEEK_END)
        tag = source.read(_TAG_SIZE)
        source.seek(_HEADER_SIZE)
        remaining = encrypted.stat().st_size - _HEADER_SIZE - _TAG_SIZE
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(header)
        with tempfile.TemporaryDirectory(prefix="phd-encrypted-drill-") as folder:
            temporary = Path(folder) / "recovered.sqlite3"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, 0o600)
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
            if stat.S_IMODE(temporary.stat().st_mode) != 0o600:
                raise PermissionError("Decrypted drill data was not stored with owner-only permissions")
            if _sha256(temporary) != sha256:
                raise ValueError("Decrypted backup does not match the independently recorded SHA-256")
            _verify_database(temporary)
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
