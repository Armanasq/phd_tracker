from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .engine import catalog, run_agent, selected
from .routing import resolve_route
from .store import ConflictError, Store

_JOB_ID = re.compile(r"^[0-9a-f]{32}$")
_FINAL = {"succeeded", "failed", "canceled"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).isoformat(timespec="seconds")


def enqueue_local_agent(
    store: Store, *, agent_id: str, input_text: str,
    provider_id: str | None = None, application_id: str | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    if not isinstance(input_text, str) or not input_text.strip() or len(input_text) > 5000:
        raise ValueError("A nonempty agent input of at most 5000 characters is required")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("Maximum attempts must be between 1 and 3")
    options = catalog(store)
    selected(options["agents"], agent_id, "agent")
    route = resolve_route(store, options["providers"], agent_id, provider_id)
    if not route.provider["local"]:
        raise PermissionError("Background queue permits local inference only; cloud execution requires separate budget and consent enforcement")
    if application_id is not None and (not isinstance(application_id, str) or len(application_id) > 160):
        raise ValueError("Invalid application ID")
    now = _iso(_utc_now())
    identity = uuid.uuid4().hex
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        occupied = store.db.execute("SELECT COUNT(*) FROM worker_jobs WHERE status IN (\'queued\',\'running\')").fetchone()[0]
        if occupied >= 100:
            raise PermissionError("Background job queue has reached its bounded capacity")
        store.db.execute(
            "INSERT INTO worker_jobs(id,agent_id,provider_id,application_id,input_text,status,"
            "attempts,max_attempts,available_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (identity, agent_id, route.provider["id"], application_id, input_text,
             "queued", 0, max_attempts, now, now, now),
        )
        store._audit("job:queued", identity)
    return job_status(store, identity)


def job_status(store: Store, identity: str) -> dict[str, Any]:
    if not isinstance(identity, str) or not _JOB_ID.fullmatch(identity):
        raise ValueError("Invalid background-job identifier")
    row = store.db.execute("SELECT * FROM worker_jobs WHERE id=?", (identity,)).fetchone()
    if row is None:
        raise ValueError("Unknown background job")
    return {
        "id": row["id"], "agent_id": row["agent_id"], "provider_id": row["provider_id"],
        "application_id": row["application_id"], "status": row["status"],
        "attempts": row["attempts"], "max_attempts": row["max_attempts"],
        "available_at": row["available_at"], "created_at": row["created_at"],
        "updated_at": row["updated_at"], "run_id": row["run_id"],
        "error_type": row["error_type"], "cancel_requested": bool(row["cancel_requested"]),
        "notice": "A running local model call cannot be forcibly interrupted; cancellation is cooperative.",
    }


def list_jobs(store: Store, *, limit: int = 30) -> list[dict[str, Any]]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid background-job list size")
    ids = store.db.execute(
        "SELECT id FROM worker_jobs ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [job_status(store, row["id"]) for row in ids]


def cancel_job(store: Store, identity: str) -> dict[str, Any]:
    job_status(store, identity)
    now = _iso(_utc_now())
    with store.db:
        row = store.db.execute("SELECT status FROM worker_jobs WHERE id=?", (identity,)).fetchone()
        if row["status"] not in _FINAL:
            updated = "canceled" if row["status"] == "queued" else row["status"]
            store.db.execute(
                "UPDATE worker_jobs SET status=?,cancel_requested=1,updated_at=? WHERE id=?",
                (updated, now, identity),
            )
            store._audit("job:cancel_requested", identity)
    return job_status(store, identity)


def claim_job(store: Store, *, now: datetime | None = None) -> tuple[str, str] | None:
    current = _iso(now or _utc_now())
    expires = _iso((now or _utc_now()) + timedelta(minutes=10))
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        store.db.execute(
            "UPDATE worker_jobs SET status='canceled',updated_at=? WHERE "
            "cancel_requested=1 AND status='running' AND lease_expires_at<=?", (current, current),
        )
        store.db.execute(
            "UPDATE worker_jobs SET status='failed',error_type='LeaseExhausted',updated_at=? "
            "WHERE status='running' AND lease_expires_at<=? AND attempts>=max_attempts",
            (current, current),
        )
        row = store.db.execute(
            "SELECT id FROM worker_jobs WHERE cancel_requested=0 AND attempts<max_attempts "
            "AND ((status='queued' AND available_at<=?) OR "
            "(status='running' AND lease_expires_at<=?)) "
            "ORDER BY created_at,id LIMIT 1", (current, current),
        ).fetchone()
        if row is None:
            return None
        token = uuid.uuid4().hex
        store.db.execute(
            "UPDATE worker_jobs SET status='running',attempts=attempts+1,"
            "lease_token=?,lease_expires_at=?,updated_at=? WHERE id=?",
            (token, expires, current, row["id"]),
        )
        store._audit("job:claimed", row["id"])
        return row["id"], token


def finish_job(store: Store, identity: str, token: str, *,
               run_id: str | None = None, error_type: str | None = None) -> dict[str, Any]:
    if not _JOB_ID.fullmatch(str(token)) or (run_id is None) == (error_type is None):
        raise ValueError("Job completion requires a lease token and one result type")
    now = _utc_now()
    with store.db:
        store.db.execute("BEGIN IMMEDIATE")
        row = store.db.execute(
            "SELECT * FROM worker_jobs WHERE id=? AND lease_token=? AND status='running'",
            (identity, token),
        ).fetchone()
        if row is None:
            raise ConflictError("Job execution lease has expired or been replaced")
        if run_id is not None:
            status = "succeeded"
            available = _iso(now)
        elif row["cancel_requested"]:
            status = "canceled"
            available = _iso(now)
        elif row["attempts"] >= row["max_attempts"]:
            status = "failed"
            available = _iso(now)
        else:
            status = "queued"
            available = _iso(now + timedelta(seconds=min(60, 10 * row["attempts"])))
        store.db.execute(
            "UPDATE worker_jobs SET status=?,available_at=?,run_id=?,error_type=?,"
            "lease_token=NULL,lease_expires_at=NULL,updated_at=? WHERE id=?",
            (status, available, run_id, error_type, _iso(now), identity),
        )
        store._audit("job:" + status, identity)
    return job_status(store, identity)


def worker_once(store: Store, root: Path) -> dict[str, Any]:
    claimed = claim_job(store)
    if claimed is None:
        return {"status": "idle"}
    identity, token = claimed
    row = store.db.execute("SELECT * FROM worker_jobs WHERE id=?", (identity,)).fetchone()
    try:
        options = catalog(store)
        route = resolve_route(store, options["providers"], row["agent_id"], row["provider_id"])
        if not route.provider["local"]:
            raise PermissionError("Provider route changed; queued local job cannot be redirected to cloud")
        result = run_agent(
            store, root, agent_id=row["agent_id"], provider_id=row["provider_id"],
            application_id=row["application_id"], input_text=row["input_text"], cloud_consent=False,
        )
        return finish_job(store, identity, token, run_id=result["id"])
    except (RuntimeError, ValueError, KeyError, PermissionError, OSError) as error:
        return finish_job(store, identity, token, error_type=type(error).__name__)
