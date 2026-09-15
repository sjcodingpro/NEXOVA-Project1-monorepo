"""
Nexova incident (support ticket) validation and analysis logic.

This module is the single source of truth for the rules defined in
CONTEXT-nexova.md. It has no dependency on FastAPI or the CLI script --
both scripts/analyze.py and the /api/incidents/analyze endpoint import
from here, so the logic is never duplicated.

Privacy: customer_email is sensitive. Nothing in this module returns or
logs an individual email address; only aggregate counts and an
"invalid_email" reason code are ever produced.
"""

import csv
import io
import re
from collections import Counter, OrderedDict

VALID_CATEGORIES = ["TECHNICAL", "BILLING", "ACCESS", "HR_QUERY", "COMPLAINT"]
VALID_STATUSES = ["OPEN", "CLOSED", "DISCARDED"]
AGENT_ID_PATTERN = re.compile(r"^AGT-\d{2}$")

REQUIRED_COLUMNS = [
    "ticket_id", "date", "client_company", "category", "description",
    "agent_id", "status", "customer_email", "satisfaction_score",
]

RULES = OrderedDict([
    ("missing_client_company", "Missing client_company"),
    ("invalid_category", "Invalid or missing category"),
    ("empty_description", "Empty or too-short description"),
    ("invalid_agent_id", "Missing or invalid agent_id"),
    ("invalid_email", "Invalid or missing email"),
    ("invalid_status", "Invalid or missing status"),
    ("closed_no_score", "Closed ticket, no score"),
    ("score_out_of_range", "Satisfaction score out of range"),
])


def load_rows_from_text(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_row(row):
    reasons = []

    if not (row.get("client_company") or "").strip():
        reasons.append("missing_client_company")

    if (row.get("category") or "").strip() not in VALID_CATEGORIES:
        reasons.append("invalid_category")

    if len((row.get("description") or "").strip()) < 5:
        reasons.append("empty_description")

    if not AGENT_ID_PATTERN.match((row.get("agent_id") or "").strip()):
        reasons.append("invalid_agent_id")

    email = (row.get("customer_email") or "").strip()
    if not email or "@" not in email:
        reasons.append("invalid_email")

    status = (row.get("status") or "").strip()
    score_raw = (row.get("satisfaction_score") or "").strip()

    # H2: VALID_STATUSES was declared but never actually checked here --
    # an out-of-domain status (e.g. "BANANA") passed validation silently
    # and then vanished from every breakdown with no warning, since
    # Counter(...) only counts what is present rather than flagging what
    # is unexpected. This affected the live /api/incidents/analyze
    # endpoint (this module), not just the CLI copy in scripts/analyze.py.
    if status not in VALID_STATUSES:
        reasons.append("invalid_status")

    if status == "CLOSED" and not score_raw:
        reasons.append("closed_no_score")

    if score_raw:
        try:
            score = int(score_raw)
            if not (1 <= score <= 5):
                reasons.append("score_out_of_range")
        except ValueError:
            reasons.append("score_out_of_range")

    return reasons


def analyze(rows):
    invalid_rule_counts = Counter()
    invalid_ticket_ids = []
    valid_rows = []

    for row in rows:
        reasons = validate_row(row)
        if reasons:
            invalid_ticket_ids.append(row.get("ticket_id", "UNKNOWN"))
            for reason in reasons:
                invalid_rule_counts[reason] += 1
        else:
            valid_rows.append(row)

    total = len(rows)
    valid_count = len(valid_rows)
    invalid_count = len(invalid_ticket_ids)

    # H1: previously used direct dict indexing here, which raises a raw
    # KeyError if a row is missing that column. router.py already
    # guards against a CSV missing the column entirely (REQUIRED_COLUMNS
    # check before this function is called), but .get() with a default
    # is defense in depth against anything that guard doesn't catch.
    category_counts = Counter(r.get("category", "") for r in valid_rows)
    status_counts = Counter(r.get("status", "") for r in valid_rows)

    closed_valid = [r for r in valid_rows if r.get("status") == "CLOSED"]
    closed_scores = [int(r["satisfaction_score"]) for r in closed_valid]
    score_distribution = Counter(closed_scores)
    avg_score = round(sum(closed_scores) / len(closed_scores), 2) if closed_scores else 0.0

    return {
        "total": total,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "invalid_rule_counts": dict(invalid_rule_counts),
        "category_counts": dict(category_counts),
        "status_counts": dict(status_counts),
        "closed_total": len(closed_valid),
        "scored_total": len(closed_scores),
        "score_distribution": dict(score_distribution),
        "avg_score": avg_score,
    }


def pct(count, total):
    if total == 0:
        return 0.0
    return round(count / total * 100, 1)


def summary_to_csv_rows(summary):
    rows = []
    rows.append(("total_records", summary["total"]))
    rows.append(("valid_records", summary["valid_count"]))
    rows.append(("invalid_records", summary["invalid_count"]))
    for key in RULES:
        rows.append((f"invalid_{key}", summary["invalid_rule_counts"].get(key, 0)))
    for cat in VALID_CATEGORIES:
        rows.append((f"category_{cat}", summary["category_counts"].get(cat, 0)))
    for st in VALID_STATUSES:
        rows.append((f"status_{st}", summary["status_counts"].get(st, 0)))
    rows.append(("closed_tickets", summary["closed_total"]))
    rows.append(("scored_tickets", summary["scored_total"]))
    rows.append(("average_satisfaction_score", summary["avg_score"]))
    for score in [1, 2, 3, 4, 5]:
        rows.append((f"satisfaction_score_{score}_count", summary["score_distribution"].get(score, 0)))
    return rows


def summary_to_csv_text(summary):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value"])
    writer.writerows(summary_to_csv_rows(summary))
    return buf.getvalue()
