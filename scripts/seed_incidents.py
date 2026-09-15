#!/usr/bin/env python3
"""
scripts/seed_incidents.py

Loads historical incidents from scripts/incidents-nexova.csv (the same
file used by the incidents-file-analyzer milestone) into the Centralized
Incident Manager's database, per CONTEXT.md's transformation rules. Every
seeded record gets origin="customer" and branch="central".

This script imports app.incidents.logic (raw CSV validation -- the exact
same 7 rules the analyzer enforces) and app.incidents.service (TinyDB
access) from services/api. It must be run with services/api's
dependencies available, e.g.:

    cd services/api
    uv run python ../../scripts/seed_incidents.py [path/to/incidents-nexova.csv]

Exits with code 1 on a critical error (missing file, unreadable CSV, DB
failure). Per-row validation/mapping failures are reported to the
console and the row is skipped -- not a critical error.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# services/api is a sibling of scripts/ at the repo root; add it to the
# path so `import app...` resolves the same way it does when uvicorn
# runs from inside services/api.
API_ROOT = Path(__file__).resolve().parent.parent / "services" / "api"
sys.path.insert(0, str(API_ROOT))

DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "incidents-nexova.csv"

STATUS_MAP = {"OPEN": "open", "CLOSED": "resolved", "DISCARDED": "discarded"}
CATEGORY_MAP = {
    "TECHNICAL": "technical_failure",
    "BILLING": "process_error",
    "ACCESS": "technical_failure",
    "HR_QUERY": "process_error",
    "COMPLAINT": "client_complaint",
}


def transform_row(row: dict) -> dict | None:
    """Applies CONTEXT.md's CSV -> model mapping. Returns a TinyDB-ready
    record dict, or None if the row can't be mapped."""
    title = (row.get("description") or "").strip()[:120].strip()
    if not title:
        return None

    model_status = STATUS_MAP.get((row.get("status") or "").strip())
    if model_status is None:
        return None

    model_category = CATEGORY_MAP.get((row.get("category") or "").strip())
    if model_category is None:
        return None

    date_raw = (row.get("date") or "").strip()
    try:
        created_at = datetime.strptime(date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    created_at_iso = created_at.isoformat()

    return {
        "title": title,
        "description": (row.get("description") or "").strip(),
        "category": model_category,
        "status": model_status,
        "origin": "customer",
        "branch": "central",
        "created_at": created_at_iso,
        "updated_at": created_at_iso,
        "seed_ticket_id": (row.get("ticket_id") or "").strip() or None,
    }


def main(csv_path: Path) -> int:
    if not csv_path.exists():
        print(f"ERROR: CSV file not found at {csv_path}", file=sys.stderr)
        return 1

    try:
        from app.incidents import logic, service
        from app.incidents.models import Branch, Category, Origin, Status
    except ImportError as exc:
        print(
            f"ERROR: could not import services/api's app package ({exc}). "
            "Run this from services/api with its dependencies installed, "
            "e.g.: cd services/api && uv run python ../../scripts/seed_incidents.py",
            file=sys.stderr,
        )
        return 1

    try:
        rows = logic.load_rows(str(csv_path))
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: could not read CSV file: {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("ERROR: CSV file has no data rows.", file=sys.stderr)
        return 1

    inserted = 0
    skipped_duplicates = 0
    invalid_rows: list[tuple[int, list[str]]] = []
    unmappable_rows: list[int] = []
    seen_ticket_ids: set[str] = set()

    for idx, row in enumerate(rows, start=2):  # +2: header is line 1
        reasons = logic.validate_row(row)  # reused, not duplicated
        if reasons:
            invalid_rows.append((idx, reasons))
            continue

        transformed = transform_row(row)
        if transformed is None:
            unmappable_rows.append(idx)
            continue

        # Sanity-check the mapped values actually land on real enum
        # members (catches a typo in STATUS_MAP/CATEGORY_MAP early,
        # rather than writing a bad record silently).
        try:
            Status(transformed["status"])
            Category(transformed["category"])
            Origin(transformed["origin"])
            Branch(transformed["branch"])
        except ValueError:
            # L2: don't interpolate the raw exception text -- low
            # sensitivity here (enum values only), but the pattern
            # invites leaking more later; name the failure instead.
            invalid_rows.append((idx, ["mapped to an invalid enum value"]))
            continue

        ticket_id = transformed["seed_ticket_id"]
        if ticket_id:
            if ticket_id in seen_ticket_ids:
                skipped_duplicates += 1
                continue
            if service.find_by_seed_ticket_id(ticket_id) is not None:
                skipped_duplicates += 1
                continue
            seen_ticket_ids.add(ticket_id)

        # H6: previously the try/except wrapped this entire loop, so a
        # bug anywhere above (transform, mapping) was reported
        # identically to a genuine DB failure here, and rows already
        # committed before a failure were never counted or reported --
        # the operator had no way to know how much of the run actually
        # landed. Narrowing the guard to just the insert call means
        # only real insert failures are caught here, and we can report
        # exactly how far the run got. Only the exception type is
        # logged, not its message -- a TinyDB serialization error's
        # message can embed the offending record, including the
        # incident description text.
        try:
            service.insert_seed_incident(transformed)
            inserted += 1
        except Exception as exc:
            print(
                f"ERROR: failed to insert the row at line {idx}, aborting. "
                f"{inserted} row(s) were committed before this failure. "
                f"({type(exc).__name__})",
                file=sys.stderr,
            )
            return 1

    print(f"Seed complete: {inserted} inserted, {skipped_duplicates} already present (skipped).")
    if invalid_rows:
        print(f"\n{len(invalid_rows)} row(s) failed CSV validation and were discarded:")
        for line_no, reasons in invalid_rows:
            print(f"  line {line_no}: {', '.join(reasons)}")
    if unmappable_rows:
        print(f"\n{len(unmappable_rows)} row(s) could not be mapped and were discarded:")
        print(f"  lines: {', '.join(str(n) for n in unmappable_rows)}")

    return 0


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    sys.exit(main(path))
