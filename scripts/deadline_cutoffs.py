from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CLOCK = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")


def verified_cutoff_utc(day: str, clock: str, zone_name: str) -> str:
    if not isinstance(day, str) or not isinstance(clock, str) or not CLOCK.fullmatch(clock):
        raise ValueError("A valid deadline date and 24-hour HH:MM clock are required")
    if not isinstance(zone_name, str) or not 1 <= len(zone_name) <= 80:
        raise ValueError("A valid IANA deadline timezone is required")
    try:
        observed_date = date.fromisoformat(day)
        if observed_date.isoformat() != day:
            raise ValueError("Noncanonical deadline date")
        zone = ZoneInfo(zone_name)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError("Deadline date or IANA timezone is invalid") from error
    hour, minute = map(int, clock.split(":"))
    local = datetime.combine(observed_date, time(hour, minute))
    candidates = set()
    for fold in (0, 1):
        aware = local.replace(tzinfo=zone, fold=fold)
        instant = aware.astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None) == local:
            candidates.add(instant)
    if len(candidates) != 1:
        raise ValueError("Deadline time is ambiguous or nonexistent in the recorded timezone")
    return candidates.pop().strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_cutoff(raw: dict, *, deadline: str | None, verification: str, source_url: str,
                     source_date: str | None, deadline_type: str, evidence: str) -> dict:
    claimed = raw.get("deadline_cutoff_verified", False)
    if type(claimed) is not bool:
        raise ValueError("deadline_cutoff_verified must be a boolean")
    clock = raw.get("deadline_time")
    zone = raw.get("deadline_timezone")
    note = raw.get("deadline_cutoff_evidence")
    provided = [value not in (None, "") for value in (clock, zone)]
    if any(provided) and not all(provided):
        raise ValueError("Deadline time and timezone must be supplied together")
    if all(provided):
        if not deadline:
            raise ValueError("A cutoff time requires a valid deadline date")
        instant = verified_cutoff_utc(deadline, clock, zone)
    else:
        if note not in (None, "") or claimed:
            raise ValueError("Cutoff evidence and verification require a time and timezone")
        instant = None
    if note not in (None, "") and (not isinstance(note, str) or len(note) > 400):
        raise ValueError("Deadline cutoff evidence must be text up to 400 characters")
    if claimed and not (verification in {"source_verified", "owner_verified"} and deadline_type == "final"
                        and source_url and source_date and evidence and isinstance(note, str) and len(note.strip()) >= 12):
        raise ValueError("Verified final cutoff requires primary-source review, observation date and specific cutoff evidence")
    return {"deadline_time": clock if instant else None,
            "deadline_timezone": zone if instant else None,
            "deadline_cutoff_evidence": note.strip() if isinstance(note, str) else "",
            "deadline_cutoff_verified": claimed,
            "deadline_cutoff_utc": instant if claimed else None}
