from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "PhD_Action_List.xlsx"
MANIFEST = ROOT / "data" / "imports" / "2026-11-06_user_upload_manifest.txt"
REPORT = ROOT / "data" / "imports" / "2026-11-06_user_upload_result.json"
COLUMNS = tuple(i for i in range(1, 22) if i not in (1, 4))
SOURCE_SHA256 = "8299fa93ca858cbc2df89108a99e071c1758b40293e833455e597c397fee2fa2"


def normalized(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return str(float(value))
    return value


def fingerprint(values):
    packed = json.dumps([normalized(v) for v in values], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()[:20]


def source_manifest(path):
    mapping = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3 or not re.fullmatch(r"[0-9a-f]+", parts[1]) or not re.fullmatch(r"[0-9a-f]{20}", parts[2]):
            raise ValueError("Malformed source manifest row: " + line[:100])
        sid, mask, digest = parts
        if sid in mapping:
            raise ValueError("Duplicate uploaded source ID: " + sid)
        mapping[sid] = (int(mask, 16), digest)
    if len(mapping) != 180:
        raise ValueError("Expected 180 uploaded source rows, found " + str(len(mapping)))
    return mapping


def reconcile(book=BOOK, manifest_path=MANIFEST, report_path=REPORT, apply=False):
    manifest = source_manifest(manifest_path)
    wb = load_workbook(book)
    if "Action list" not in wb or wb["Action list"]["U3"].value != "Source id":
        raise ValueError("Unexpected original workbook schema")
    ws = wb["Action list"]
    byid = {}
    for row in range(4, ws.max_row + 1):
        sid = ws.cell(row, 21).value
        if sid:
            if str(sid) in byid:
                raise ValueError("Duplicate workbook source ID: " + str(sid))
            byid[str(sid)] = row
    missing = [sid for sid in manifest if sid not in byid]
    if missing:
        raise ValueError("Uploaded source IDs absent from repository: " + str(missing[:20]))
    changes = []
    mismatches = []
    for sid, (mask, digest) in manifest.items():
        row = byid[sid]
        for col in COLUMNS:
            if mask & (1 << (col - 1)):
                cell = ws.cell(row, col)
                if cell.value is not None or cell.hyperlink is not None:
                    changes.append({"source_id": sid, "row": row, "column": col})
                    cell.hyperlink = None
                    cell.value = None
        actual = fingerprint([ws.cell(row, c).value for c in COLUMNS])
        if actual != digest:
            mismatches.append({"source_id": sid, "row": row, "expected": digest, "actual": actual})
    extra_ids = sorted(set(byid) - set(manifest))
    report = {
        "status": "verified" if not mismatches else "mismatch",
        "uploaded_source_file_sha256": SOURCE_SHA256,
        "original_uploaded_applications": len(manifest),
        "additional_repository_applications_retained": extra_ids,
        "blank_cells_corrected": len(changes),
        "corrected_cells": changes,
        "mismatched_original_records": mismatches,
        "policy": "Uploaded data is authoritative for its original 180 records. Additional verified repository-only records remain intact. Never infer submission from a vacancy.",
    }
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mismatches:
        raise ValueError("Source data differs in " + str(len(mismatches)) + " nonblank rows; manual reconciliation required: " + str([x["source_id"] for x in mismatches[:30]]))
    if apply and changes:
        wb.save(book)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workbook", type=Path, default=BOOK)
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--report", type=Path, default=REPORT)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    result = reconcile(a.workbook, a.manifest, a.report, a.apply)
    print(json.dumps({
        "status": result["status"],
        "original_rows": result["original_uploaded_applications"],
        "additional_preserved": result["additional_repository_applications_retained"],
        "blank_cells_corrected": result["blank_cells_corrected"],
    }))


if __name__ == "__main__":
    main()
