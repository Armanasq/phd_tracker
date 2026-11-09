from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STATUS = {"unconfirmed", "shortlisted", "preparing", "submitted", "interview", "offer", "rejected", "withdrawn", "blocked", "archived"}
CONTACT = {"unrecorded", "to_contact", "contacted", "awaiting_reply", "followup_due", "replied", "declined", "completed"}
DOCUMENT = {"unknown", "ready", "in_progress", "not_started", "not_applicable"}
ALLOWED_UPDATE = {"status", "contact_status", "followup", "priority", "next_step", "notes", "receipt", "document_states", "confirmed_submission", "referees", "estimated_hours", "evidence_flags"}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def default_path() -> Path:
    base = os.environ.get("PHDAI_PRIVATE_DIR")
    return (Path(base).expanduser() if base else Path.home() / ".local" / "share" / "phd-atlas") / "state.sqlite3"

class ConflictError(ValueError):
    pass

class Store:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.path.exists():
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if self.path.is_symlink() or not self.path.is_file():
            raise PermissionError("Private SQLite state must be an ordinary file, not a symlink")
        if stat.S_IMODE(self.path.stat().st_mode) & 0o077:
            raise PermissionError("Unsafe state database permissions; run chmod 600 on the private SQLite file")
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS catalog(kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS applications(id TEXT PRIMARY KEY, payload TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, kind TEXT NOT NULL, agent_id TEXT NOT NULL, application_id TEXT, status TEXT NOT NULL, provider_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, subject TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schedule(id TEXT PRIMARY KEY, last_period TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schedule_claims(id TEXT PRIMARY KEY, period TEXT NOT NULL, token TEXT NOT NULL, claimed_at TEXT NOT NULL, expires_at TEXT NOT NULL, cloud_calls INTEGER NOT NULL, day_start TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS request_idempotency(key TEXT PRIMARY KEY, endpoint TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, response TEXT, expires_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_schedule_claims_active ON schedule_claims(day_start,expires_at);
        CREATE TABLE IF NOT EXISTS private_objects(kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS conversations(
            id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, application_id TEXT,
            title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversation_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL
            REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL,
            content TEXT NOT NULL, model TEXT, provider_id TEXT, run_id TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_conversation_messages ON conversation_messages(conversation_id,id);
        CREATE INDEX IF NOT EXISTS idx_conversations_recent ON conversations(updated_at DESC);

        """)
        self.db.commit()

    def diagnostics(self) -> dict[str, Any]:
        quick = self.db.execute("PRAGMA quick_check(1)").fetchone()[0]
        foreign = self.db.execute("PRAGMA foreign_key_check").fetchall()
        journal = self.db.execute("PRAGMA journal_mode").fetchone()[0]
        current = utcnow()
        leases = self.db.execute(
            "SELECT COUNT(*) FROM schedule_claims WHERE expires_at>?", (current,)
        ).fetchone()[0]
        rows = self.db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        backups = self.path.parent / "backups"
        backup_count = len(list(backups.glob("phd-atlas-*.sqlite3"))) if backups.is_dir() and not backups.is_symlink() else 0
        permission = stat.S_IMODE(self.path.stat().st_mode)
        return {
            "schema_version": 1,
            "status": "ok" if quick == "ok" and not foreign else "degraded",
            "database": {
                "integrity": str(quick)[:200],
                "foreign_key_violations": len(foreign),
                "journal_mode": journal,
                "private_file_mode": oct(permission),
                "size_bytes": self.path.stat().st_size,
                "application_overrides": rows,
            },
            "scheduler": {"active_claims": leases},
            "backups": {"count": backup_count, "directory_private": backups.is_dir() and not backups.is_symlink()},
        }

    def create_backup(self, *, retain: int = 7) -> dict[str, Any]:
        if type(retain) is not int or not 1 <= retain <= 30:
            raise ValueError("Backup retention must be an integer between 1 and 30")
        directory = self.path.parent / "backups"
        if directory.is_symlink():
            raise PermissionError("Backup directory cannot be a symlink")
        directory.mkdir(mode=0o700, parents=False, exist_ok=True)
        if not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
            raise PermissionError("Backup directory must have owner-only permissions")
        created = datetime.now(timezone.utc)
        name = "phd-atlas-" + created.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10] + ".sqlite3"
        target = directory / name
        fd, temporary = tempfile.mkstemp(prefix=".phd-atlas-", suffix=".tmp", dir=directory)
        os.close(fd)
        try:
            destination = sqlite3.connect(temporary)
            try:
                self.db.backup(destination, pages=100, sleep=0.05)
                quick = destination.execute("PRAGMA quick_check(1)").fetchone()[0]
                if quick != "ok" or destination.execute("PRAGMA foreign_key_check").fetchone():
                    raise RuntimeError("SQLite backup integrity verification failed")
            finally:
                destination.close()
            if stat.S_IMODE(Path(temporary).stat().st_mode) != 0o600:
                os.chmod(temporary, 0o600)
            os.replace(temporary, target)
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            files = sorted(
                (q for q in directory.glob("phd-atlas-*.sqlite3") if q.is_file() and not q.is_symlink()),
                key=lambda q: q.stat().st_mtime_ns, reverse=True,
            )
            for expired in files[retain:]:
                expired.unlink()
            digest = hashlib.sha256()
            with target.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            self._audit("state:backup", name)
            self.db.commit()
            return {
                "filename": name,
                "directory": str(directory),
                "created_at": created.isoformat(timespec="seconds"),
                "size_bytes": target.stat().st_size,
                "sha256": digest.hexdigest(),
                "integrity": "ok",
                "retained": min(len(files), retain),
                "includes_credentials": False,
            }
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def close(self) -> None:
        self.db.close()

    def begin_idempotent(
        self, key: str, endpoint: str, payload: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{16,128}", key):
            raise ValueError("Idempotency-Key must contain 16–128 safe characters")
        if endpoint not in {"/api/agents/run", "/api/workflows/run"}:
            raise ValueError("Idempotency is unavailable for this endpoint")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc)
        cutoff = now.isoformat(timespec="seconds")
        lease_until = (now + timedelta(minutes=15)).isoformat(timespec="seconds")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute("DELETE FROM request_idempotency WHERE expires_at<=?", (cutoff,))
            row = self.db.execute(
                "SELECT endpoint,digest,state,response FROM request_idempotency WHERE key=?", (key,)
            ).fetchone()
            if row:
                if row["endpoint"] != endpoint or row["digest"] != digest:
                    raise ConflictError("Idempotency key was already used with another request")
                if row["state"] == "completed" and row["response"]:
                    return "replayed", json.loads(row["response"])
                return "running", None
            self.db.execute(
                "INSERT INTO request_idempotency(key,endpoint,digest,state,response,expires_at) VALUES(?,?,?,?,?,?)",
                (key, endpoint, digest, "running", None, lease_until),
            )
        return "claimed", None

    def complete_idempotent(self, key: str, response: dict[str, Any]) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
        with self.db:
            updated = self.db.execute(
                "UPDATE request_idempotency SET state='completed',response=?,expires_at=? "
                "WHERE key=? AND state='running'",
                (json.dumps(response, ensure_ascii=False), expires, key),
            ).rowcount
            if updated != 1:
                raise ConflictError("Idempotent request lease no longer exists")

    def abort_idempotent(self, key: str) -> None:
        with self.db:
            self.db.execute(
                "DELETE FROM request_idempotency WHERE key=? AND state='running'", (key,)
            )

    def get_custom(self, kind: str) -> list[dict[str, Any]]:
        if kind not in {"provider", "agent", "workflow", "connection", "setting"}:
            raise ValueError("Invalid catalog kind")
        rows = self.db.execute("SELECT payload FROM catalog WHERE kind=? ORDER BY id", (kind,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def put_custom(self, kind: str, entry: dict[str, Any]) -> None:
        if kind not in {"provider", "agent", "workflow", "connection", "setting"}:
            raise ValueError("Invalid catalog kind")
        with self.db:
            self.db.execute("INSERT INTO catalog(kind,id,payload,updated_at) VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                            (kind, entry["id"], json.dumps(entry), utcnow()))
            if kind == "provider":
                self.db.execute("DELETE FROM catalog WHERE kind='connection' AND id=?", (entry["id"],))
                settings_row = self.db.execute("SELECT payload FROM catalog WHERE kind='setting' AND id='preferences'").fetchone()
                if settings_row:
                    preferences = json.loads(settings_row["payload"])
                    approved = preferences.get("approved_cloud_providers", [])
                    if entry["id"] in approved:
                        preferences["approved_cloud_providers"] = [p for p in approved if p != entry["id"]]
                        self.db.execute("UPDATE catalog SET payload=?,updated_at=? WHERE kind='setting' AND id='preferences'",
                                        (json.dumps(preferences), utcnow()))
            self._audit("catalog:" + kind, entry["id"])

    def catalog(self, kind: str, defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values = {entry["id"]: dict(entry) for entry in defaults}
        for entry in self.get_custom(kind):
            values[entry["id"]] = entry
        return list(values.values())

    def get_application(self, identity: str) -> dict[str, Any]:
        row = self.db.execute("SELECT payload,version FROM applications WHERE id=?", (identity,)).fetchone()
        return {"version": int(row["version"]), **json.loads(row["payload"])} if row else {"version": 0}

    def update_application(self, identity: str, patch: dict[str, Any], expected_version: int) -> dict[str, Any]:
        if not patch or set(patch) - ALLOWED_UPDATE:
            raise ValueError("Unknown application update fields")
        current = self.get_application(identity)
        if current["version"] != expected_version:
            raise ConflictError("Application state changed; reload before saving")
        if "status" in patch and patch["status"] not in STATUS:
            raise ValueError("Invalid application status")
        if "contact_status" in patch and patch["contact_status"] not in CONTACT:
            raise ValueError("Invalid contact status")
        if "priority" in patch and patch["priority"] not in {"high", "normal", "low"}:
            raise ValueError("Invalid priority")
        if "document_states" in patch:
            documents = patch["document_states"]
            if (
                not isinstance(documents, dict) or len(documents) > 30
                or any(not isinstance(k, str) or not 1 <= len(k) <= 120 or any(ord(c) < 32 for c in k) for k in documents)
                or any(not isinstance(v, str) or v not in DOCUMENT for v in documents.values())
            ):
                raise ValueError("Invalid document readiness state")
        if "estimated_hours" in patch and patch["estimated_hours"] is not None and (not isinstance(patch["estimated_hours"], (int, float)) or isinstance(patch["estimated_hours"], bool) or not 0 <= patch["estimated_hours"] <= 400):
            raise ValueError("Invalid effort estimate")
        if "followup" in patch and patch["followup"] not in (None, ""):
            from datetime import date
            date.fromisoformat(str(patch["followup"]))
        for key in ("notes", "next_step", "receipt"):
            if key in patch and (not isinstance(patch[key], str) or len(patch[key]) > 3000):
                raise ValueError("Invalid " + key)
        if "referees" in patch and (not isinstance(patch["referees"], list) or len(patch["referees"]) > 20):
            raise ValueError("Invalid referee tracking structure")
        if "evidence_flags" in patch and (not isinstance(patch["evidence_flags"], list) or len(patch["evidence_flags"]) > 30):
            raise ValueError("Invalid evidence flags")
        updated = {k: v for k, v in current.items() if k != "version"}
        updated.update(patch)
        if updated.get("status") == "submitted" and current.get("status") != "submitted":
            if patch.get("confirmed_submission") is not True:
                raise ValueError("Submission requires explicit owner confirmation")
        updated.pop("confirmed_submission", None)
        version = current["version"] + 1
        encoded = json.dumps(updated, ensure_ascii=False)
        with self.db:
            if expected_version == 0:
                try:
                    self.db.execute(
                        "INSERT INTO applications(id,payload,version,updated_at) VALUES(?,?,?,?)",
                        (identity, encoded, version, utcnow()),
                    )
                except sqlite3.IntegrityError as error:
                    raise ConflictError("Concurrent application creation; reload") from error
            else:
                changed = self.db.execute(
                    "UPDATE applications SET payload=?,version=?,updated_at=? WHERE id=? AND version=?",
                    (encoded, version, utcnow(), identity, expected_version),
                ).rowcount
                if changed != 1:
                    raise ConflictError("Concurrent application update; reload")
            self._audit("application:update", identity)
        return {"id": identity, "version": version, **updated}

    def list_applications(self) -> dict[str, dict[str, Any]]:
        rows = self.db.execute("SELECT id,payload,version FROM applications").fetchall()
        return {row["id"]: {"version": row["version"], **json.loads(row["payload"])} for row in rows}

    def put_run(self, kind: str, agent_id: str, application_id: str | None, status: str, provider_id: str, payload: dict[str, Any]) -> str:
        identity = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO runs(id,kind,agent_id,application_id,status,provider_id,payload,created_at) VALUES(?,?,?,?,?,?,?,?)",
                            (identity, kind, agent_id, application_id, status, provider_id, json.dumps(payload, ensure_ascii=False), utcnow()))
            self._audit("run:" + status, agent_id)
        return identity

    def runs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM runs ORDER BY created_at DESC, rowid DESC LIMIT ?", (min(max(limit, 1), 100),)).fetchall()
        return [{"id": r["id"], "kind": r["kind"], "agent_id": r["agent_id"], "application_id": r["application_id"],
                 "status": r["status"], "provider_id": r["provider_id"], "created_at": r["created_at"], **json.loads(r["payload"])} for r in rows]


    def conversation(self, conversation_id: str) -> dict[str, Any]:
        if not isinstance(conversation_id, str) or len(conversation_id) != 32:
            raise ValueError("Invalid conversation identifier")
        try:
            uuid.UUID(hex=conversation_id)
        except ValueError as error:
            raise ValueError("Invalid conversation identifier") from error
        row = self.db.execute(
            "SELECT id,agent_id,application_id,title,created_at,updated_at FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown conversation")
        messages = self.db.execute(
            "SELECT m.role,m.content,m.model,m.provider_id,m.run_id,m.created_at,r.payload AS run_payload "
            "FROM conversation_messages AS m LEFT JOIN runs AS r ON r.id=m.run_id "
            "WHERE m.conversation_id=? ORDER BY m.id DESC LIMIT 300", (conversation_id,),
        ).fetchall()
        visible = []
        for message in reversed(messages):
            item = dict(message)
            payload = json.loads(item.pop("run_payload")) if item.get("run_payload") else {}
            if item["role"] == "assistant":
                item["evidence_refs"] = payload.get("evidence_refs", [])
                item["retrieval_method"] = payload.get("retrieval_method")
                item["latency_ms"] = payload.get("latency_ms")
                item["source_as_of"] = payload.get("source_as_of")
                item["tools"] = payload.get("tools", [])
            visible.append(item)
        return {**dict(row), "messages": visible}

    def conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id,agent_id,application_id,title,created_at,updated_at "
            "FROM conversations ORDER BY updated_at DESC,id DESC LIMIT ?",
            (min(max(limit, 1), 50),),
        ).fetchall()
        return [dict(row) for row in rows]

    def conversation_context(
        self, conversation_id: str, agent_id: str, application_id: str | None,
        *, limit: int = 6,
    ) -> list[dict[str, str]]:
        conversation = self.conversation(conversation_id)
        if conversation["agent_id"] != agent_id or conversation["application_id"] != application_id:
            raise ValueError("Conversation is scoped to another agent or application")
        rows = self.db.execute(
            "SELECT role,content FROM conversation_messages WHERE conversation_id=? "
            "ORDER BY id DESC LIMIT ?", (conversation_id, min(max(limit, 1), 12)),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"][:750]} for row in reversed(rows)]

    def save_conversation_turn(
        self, *, conversation_id: str | None, agent_id: str, application_id: str | None,
        question: str, answer: str, model: str, provider_id: str, run_id: str,
    ) -> str:
        if not isinstance(question, str) or not question.strip() or len(question) > 5000:
            raise ValueError("Invalid conversation question")
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 20000:
            raise ValueError("Invalid conversation answer")
        if conversation_id:
            self.conversation_context(conversation_id, agent_id, application_id, limit=1)
        identity = conversation_id or uuid.uuid4().hex
        timestamp = utcnow()
        with self.db:
            if not conversation_id:
                self.db.execute(
                    "INSERT INTO conversations(id,agent_id,application_id,title,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?)",
                    (identity, agent_id, application_id, question.strip()[:110], timestamp, timestamp),
                )
            for role, content in (("user", question), ("assistant", answer)):
                self.db.execute(
                    "INSERT INTO conversation_messages(conversation_id,role,content,model,provider_id,run_id,created_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (identity, role, content, model if role == "assistant" else None,
                     provider_id if role == "assistant" else None,
                     run_id if role == "assistant" else None, timestamp),
                )
            self.db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (timestamp, identity))
        return identity

    def delete_conversation(self, conversation_id: str) -> bool:
        self.conversation(conversation_id)
        with self.db:
            changed = self.db.execute("DELETE FROM conversations WHERE id=?", (conversation_id,)).rowcount
            if changed:
                self._audit("conversation:deleted", conversation_id)
        return bool(changed)

    def count_runs_since(self, since: str, provider_ids: list[str]) -> int:
        if not provider_ids:
            return 0
        query = "SELECT COUNT(*) FROM runs WHERE created_at >= ? AND status IN ('proposed','failed') AND provider_id IN (" + ",".join("?" for _ in provider_ids) + ")"
        return int(self.db.execute(query, [since, *provider_ids]).fetchone()[0])

    def schedule_claim(
        self, identity: str, period: str, *, now: datetime | None = None,
        lease_seconds: int = 900, cloud_calls: int = 0, cloud_cap: int = 0,
        cloud_ids: list[str] | None = None, day_start: str = "",
    ) -> tuple[str | None, str]:
        if not isinstance(identity, str) or not identity or len(identity) > 100:
            raise ValueError("Invalid scheduled workflow ID")
        if not isinstance(period, str) or not period or len(period) > 50:
            raise ValueError("Invalid scheduled period")
        if not 30 <= lease_seconds <= 3600:
            raise ValueError("Invalid schedule lease duration")
        if type(cloud_calls) is not int or cloud_calls < 0 or cloud_calls > 3:
            raise ValueError("Invalid reserved cloud call count")
        if cloud_calls and (cloud_cap < 1 or not cloud_ids or not day_start):
            return None, "cloud_budget_disabled"
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        timestamp = current.isoformat(timespec="seconds")
        expires = (current + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
        token = uuid.uuid4().hex
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            done = self.db.execute("SELECT last_period FROM schedule WHERE id=?", (identity,)).fetchone()
            if done and done["last_period"] == period:
                return None, "already_executed"
            active = self.db.execute(
                "SELECT token,expires_at,period FROM schedule_claims WHERE id=?", (identity,)
            ).fetchone()
            if active and active["expires_at"] > timestamp and active["period"] == period:
                return None, "already_running"
            if cloud_calls:
                billed = self.count_runs_since(day_start, cloud_ids or [])
                reserved = self.db.execute(
                    "SELECT COALESCE(SUM(cloud_calls),0) AS n FROM schedule_claims "
                    "WHERE expires_at>? AND day_start=? AND id<>?",
                    (timestamp, day_start, identity),
                ).fetchone()["n"]
                if billed + reserved + cloud_calls > cloud_cap:
                    return None, "daily_cloud_model_call_cap"
            self.db.execute(
                "INSERT INTO schedule_claims(id,period,token,claimed_at,expires_at,cloud_calls,day_start) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "period=excluded.period,token=excluded.token,claimed_at=excluded.claimed_at,"
                "expires_at=excluded.expires_at,cloud_calls=excluded.cloud_calls,day_start=excluded.day_start",
                (identity, period, token, timestamp, expires, cloud_calls, day_start),
            )
        return token, "claimed"

    def schedule_release(self, identity: str, period: str, token: str) -> bool:
        with self.db:
            changed = self.db.execute(
                "DELETE FROM schedule_claims WHERE id=? AND period=? AND token=?",
                (identity, period, token),
            ).rowcount
        return bool(changed)

    def schedule_complete(self, identity: str, period: str, token: str) -> None:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            claim = self.db.execute(
                "SELECT token FROM schedule_claims WHERE id=? AND period=?", (identity, period)
            ).fetchone()
            if claim is None or claim["token"] != token:
                raise ConflictError("Scheduled workflow lease was replaced; completion not recorded")
            self.db.execute(
                "INSERT INTO schedule(id,last_period,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET last_period=excluded.last_period,updated_at=excluded.updated_at",
                (identity, period, utcnow()),
            )
            self.db.execute(
                "DELETE FROM schedule_claims WHERE id=? AND period=? AND token=?", (identity, period, token)
            )
            self._audit("schedule:ran", identity)

    def schedule_last(self, identity: str) -> str | None:
        row = self.db.execute("SELECT last_period FROM schedule WHERE id=?", (identity,)).fetchone()
        return str(row["last_period"]) if row else None

    def schedule_mark(self, identity: str, period: str) -> None:
        with self.db:
            self.db.execute("INSERT INTO schedule(id,last_period,updated_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET last_period=excluded.last_period,updated_at=excluded.updated_at",
                            (identity, period, utcnow()))
            self._audit("schedule:ran", identity)

    def _audit(self, action: str, subject: str) -> None:
        self.db.execute("INSERT INTO audit(action,subject,created_at) VALUES(?,?,?)", (action, subject, utcnow()))

    def put_item(self, kind: str, value: dict[str, Any]) -> dict[str, Any]:
        from .operations import normalize_item
        entry = normalize_item(kind, value)
        with self.db:
            self.db.execute("INSERT INTO private_objects(kind,id,payload,updated_at) VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                            (kind, entry["id"], json.dumps(entry, ensure_ascii=False), utcnow()))
            self._audit("private:" + kind + ":upsert", entry["id"])
        return entry

    def items(self, kind: str) -> list[dict[str, Any]]:
        from .operations import KINDS
        if kind not in KINDS:
            raise ValueError("Unknown private record kind")
        rows = self.db.execute("SELECT payload FROM private_objects WHERE kind=? ORDER BY id", (kind,)).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def delete_item(self, kind: str, identity: str) -> bool:
        from .operations import KINDS
        if kind not in KINDS:
            raise ValueError("Unknown private record kind")
        with self.db:
            cursor = self.db.execute("DELETE FROM private_objects WHERE kind=? AND id=?", (kind, identity))
            if cursor.rowcount:
                self._audit("private:" + kind + ":delete", identity)
        return bool(cursor.rowcount)

    def activity(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT action,subject,created_at FROM audit ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 100),)).fetchall()
        return [dict(r) for r in rows]
