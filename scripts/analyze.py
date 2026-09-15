#!/usr/bin/env python3
"""
Nexova -- Support Ticket (Incident) Analyzer

Reads a support-incident CSV export, validates each record against the
rules defined in CONTEXT-nexova.md, and prints a summary of the ticket
backlog: category breakdown, status breakdown, and satisfaction index
for closed tickets.

Privacy: customer_email is sensitive. This script never prints, logs,
or exports an individual email address in any output, including the
invalid-record detail.

Usage:
    python analyze.py incidents-nexova.csv
"""

import csv
import re
import sys
from collections import Counter, OrderedDict

VALID_CATEGORIES = ["TECHNICAL", "BILLING", "ACCESS", "HR_QUERY", "COMPLAINT"]
VALID_STATUSES = ["OPEN", "CLOSED", "DISCARDED"]
AGENT_ID_PATTERN = re.compile(r"^AGT-\d{2}$")

# Mirrors services/api/app/incidents/logic.py's REQUIRED_COLUMNS -- the API
# endpoint already rejects a CSV missing one of these (router.py); this
# script had no equivalent check, which is what let a malformed file reach
# analyze() and crash there instead of failing cleanly up front.
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
    # Counter(...) only counts what's present rather than flagging what's
    # unexpected.
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

    # H1: r["status"] / r["category"] / r["satisfaction_score"] previously
    # used direct dict indexing, which raises a raw KeyError if a row
    # (or the whole CSV) is missing that column. .get() with a sensible
    # default means a malformed row can never crash this far downstream --
    # the REQUIRED_COLUMNS check in main() is still the primary guard for
    # a missing column entirely, this is defense in depth for anything
    # that check doesn't catch.
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
        "invalid_rule_counts": invalid_rule_counts,
        "category_counts": category_counts,
        "status_counts": status_counts,
        "closed_total": len(closed_valid),
        "scored_total": len(closed_scores),
        "score_distribution": score_distribution,
        "avg_score": avg_score,
    }


def pct(count, total):
    if total == 0:
        return 0.0
    return round(count / total * 100, 1)


def dotted_line(label, value, prefix="  ", width=46):
    text = f"{prefix}{label} "
    pad_len = max(1, width - len(text) - len(str(value)))
    return f"{text}{'.' * pad_len} {value}"


def format_console(summary, source_file):
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append("  NEXOVA -- SUPPORT TICKET ANALYSIS")
    lines.append(f"  Source file: {source_file}")
    lines.append(sep)
    lines.append("")

    lines.append(dotted_line("TOTAL RECORDS IN FILE", summary["total"], prefix=""))
    lines.append(f"  \u251c\u2500 Valid records {'.' * 16} {summary['valid_count']}")
    lines.append(f"  \u2514\u2500 Invalid / incomplete {'.' * 9} {summary['invalid_count']}")
    lines.append("")

    lines.append("INVALID RECORDS BREAKDOWN")
    rule_items = [(key, label) for key, label in RULES.items()
                  if summary["invalid_rule_counts"].get(key, 0) > 0]
    for i, (key, label) in enumerate(rule_items):
        count = summary["invalid_rule_counts"][key]
        connector = "\u2514\u2500" if i == len(rule_items) - 1 else "\u251c\u2500"
        padded_label = label + " " + "." * max(1, 30 - len(label))
        lines.append(f"  {connector} {padded_label} {count}")
    if not rule_items:
        lines.append("  (no invalid records)")
    lines.append("")

    lines.append("BREAKDOWN BY CATEGORY (valid records)")
    for i, cat in enumerate(VALID_CATEGORIES):
        count = summary["category_counts"].get(cat, 0)
        percentage = pct(count, summary["valid_count"])
        connector = "\u2514\u2500" if i == len(VALID_CATEGORIES) - 1 else "\u251c\u2500"
        padded_label = cat + " " + "." * max(1, 20 - len(cat))
        lines.append(f"  {connector} {padded_label} {count:>3}  ({percentage}%)")
    lines.append("")

    lines.append("BREAKDOWN BY STATUS (valid records)")
    for i, st in enumerate(VALID_STATUSES):
        count = summary["status_counts"].get(st, 0)
        percentage = pct(count, summary["valid_count"])
        connector = "\u2514\u2500" if i == len(VALID_STATUSES) - 1 else "\u251c\u2500"
        padded_label = st + " " + "." * max(1, 20 - len(st))
        lines.append(f"  {connector} {padded_label} {count:>3}  ({percentage}%)")
    lines.append("")

    lines.append("SATISFACTION INDEX (closed tickets)")
    lines.append(f"  Scored tickets: {summary['scored_total']} of {summary['closed_total']}")
    lines.append(f"  Average score: {summary['avg_score']:.2f} / 5.00")
    score_labels = {
        1: "Score 1 (Very dissatisfied)",
        2: "Score 2 (Dissatisfied)",
        3: "Score 3 (Neutral)",
        4: "Score 4 (Satisfied)",
        5: "Score 5 (Very satisfied)",
    }
    for i, score in enumerate([1, 2, 3, 4, 5]):
        count = summary["score_distribution"].get(score, 0)
        connector = "\u2514\u2500" if i == 4 else "\u251c\u2500"
        label = score_labels[score]
        padded_label = label + " " + "." * max(1, 34 - len(label))
        lines.append(f"  {connector} {padded_label} {count}")
    lines.append("")
    lines.append(sep)

    return "\n".join(lines)


def export_results_csv(summary, out_path="results.csv"):
    """Write one row per metric. No individual customer data is ever included."""
    rows = []
    rows.append(("total_records", summary["total"]))
    rows.append(("valid_records", summary["valid_count"]))
    rows.append(("invalid_records", summary["invalid_count"]))
    for key, label in RULES.items():
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

    # M9: an unguarded open(..., "w") raised a raw PermissionError
    # traceback if the target path wasn't writable (e.g. a read-only
    # directory, or out_path pointing somewhere the user can't write).
    try:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            writer.writerows(rows)
    except OSError as exc:
        print(f"Error: could not write results to {out_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    return out_path


def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <path-to-csv>")
        sys.exit(1)

    path = sys.argv[1]

    try:
        rows = load_rows(path)
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        sys.exit(1)
    except (OSError, csv.Error) as exc:
        print(f"Error: could not read {path}: {exc}")
        sys.exit(1)

    # H1 (primary guard) + M10: a header-only or empty CSV previously
    # exited 0 and produced an all-zeros report as if it were real data --
    # the API rejects the same input with a 400 (router.py); the CLI
    # should treat it as equally critical instead of silently "succeeding".
    if not rows:
        print(f"Error: {path} has no data rows.")
        sys.exit(1)

    missing_columns = [c for c in REQUIRED_COLUMNS if c not in rows[0].keys()]
    if missing_columns:
        print(f"Error: {path} is missing required columns: {', '.join(missing_columns)}")
        sys.exit(1)

    summary = analyze(rows)
    print(format_console(summary, source_file=path.split("/")[-1]))

    # M9: input() raises EOFError when stdin is closed/piped (e.g. `< /dev/null`,
    # a CI runner, or any non-interactive invocation) -- previously this
    # crashed with a raw traceback *after* the analysis had already printed
    # successfully, and exited 1 for what was otherwise a successful run.
    try:
        answer = input("Export results to CSV? [y / n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo input available -- skipping CSV export.")
        return

    if answer == "y":
        out_path = export_results_csv(summary)
        print(f"Results exported to {out_path}")


if __name__ == "__main__":
    main()
