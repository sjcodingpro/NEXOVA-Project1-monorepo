"""
Seeder for the Nexova supplier directory (TinyDB).

Loads the exact initial supplier list from CONTEXT-nexova.md. Idempotent:
running this more than once will not create duplicate suppliers --
existing suppliers are matched by name before inserting.

Usage:
    uv run seed
"""

import sys
from datetime import datetime, timezone

from app.database import get_suppliers_table
from app.suppliers.models import SupplierCreate

SUPPLIERS_SEED = [
    {
        "name": "LinkedIn Talent Solutions",
        "country": "Spain",
        "categories": ["job_boards"],
        "monthly_rate": 1200.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2025-03-31",
        "contact_email": "account@linkedin.com",
        "notes": "Corporate license for job posting and candidate search.",
    },
    {
        "name": "InfoJobs Premium",
        "country": "Spain",
        "categories": ["job_boards"],
        "monthly_rate": 490.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2025-06-30",
        "contact_email": "empresas@infojobs.net",
    },
    {
        "name": "Indeed Sponsored",
        "country": "USA",
        "categories": ["job_boards"],
        "monthly_rate": 850.0,
        "currency": "USD",
        "status": "active",
        "contact_email": "sales@indeed.com",
        "notes": "Pay-per-click campaigns for customer support profiles in Miami.",
    },
    {
        "name": "Workable",
        "country": "Spain",
        "categories": ["ats_software"],
        "monthly_rate": 299.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2025-09-15",
        "contact_email": "support@workable.com",
        "notes": "Primary ATS for the Valencia selection team.",
    },
    {
        "name": "Greenhouse",
        "country": "USA",
        "categories": ["ats_software"],
        "monthly_rate": 620.0,
        "currency": "USD",
        "status": "suspended",
        "contact_email": "accounts@greenhouse.io",
        "notes": "Suspended after non-renewal. Sergio is evaluating migrating everything to Workable.",
    },
    {
        "name": "Thomas International",
        "country": "Spain",
        "categories": ["assessment_tools"],
        "monthly_rate": 380.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2025-12-01",
        "contact_email": "clientes@thomas.es",
        "notes": "Personality and aptitude tests for middle-management hiring processes.",
    },
    {
        "name": "HireVue",
        "country": "USA",
        "categories": ["video_interview"],
        "monthly_rate": 540.0,
        "currency": "USD",
        "status": "active",
        "contract_renewal_date": "2025-08-31",
        "contact_email": "support@hirevue.com",
    },
    {
        "name": "Udemy Business",
        "country": "Spain",
        "categories": ["training_platforms"],
        "monthly_rate": 420.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2026-01-15",
        "contact_email": "business@udemy.com",
        "notes": "Licenses for the internal team. Managed by Elena Vargas.",
    },
    {
        "name": "Coursera for Teams",
        "country": "USA",
        "categories": ["training_platforms"],
        "monthly_rate": 399.0,
        "currency": "USD",
        "status": "suspended",
        "contact_email": "teams@coursera.com",
        "notes": "Suspended due to low usage. Review before Q4.",
    },
    {
        "name": "Sage HR",
        "country": "Spain",
        "categories": ["payroll_and_hr_software"],
        "monthly_rate": 310.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2025-10-01",
        "contact_email": "soporte@sage.com",
        "notes": "Payroll and personnel management software for the Valencia headquarters.",
    },
    {
        "name": "Gusto",
        "country": "USA",
        "categories": ["payroll_and_hr_software"],
        "monthly_rate": 280.0,
        "currency": "USD",
        "status": "active",
        "contact_email": "support@gusto.com",
        "notes": "Payroll management for Miami office employees.",
    },
    {
        "name": "Checkr",
        "country": "USA",
        "categories": ["background_check"],
        "monthly_rate": 195.0,
        "currency": "USD",
        "status": "active",
        "contract_renewal_date": "2025-11-30",
        "contact_email": "sales@checkr.com",
    },
    {
        "name": "Microsoft 365 Business",
        "country": "Spain",
        "categories": ["it_and_software_licenses"],
        "monthly_rate": 760.0,
        "currency": "EUR",
        "status": "active",
        "contact_email": "enterprise@microsoft.com",
        "notes": "Licenses for the entire Valencia and Miami workforce.",
    },
    {
        "name": "Regus Valencia",
        "country": "Spain",
        "categories": ["office_and_facilities"],
        "monthly_rate": 2400.0,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2025-07-01",
        "contact_email": "valencia@regus.com",
        "notes": "Lease for the main Valencia office. Includes meeting room.",
    },
    {
        "name": "WeWork Miami",
        "country": "USA",
        "categories": ["office_and_facilities"],
        "monthly_rate": 3100.0,
        "currency": "USD",
        "status": "active",
        "contract_renewal_date": "2025-09-30",
        "contact_email": "miami@wework.com",
    },
]


def main() -> int:
    # M11: get_suppliers_table() (and TinyDB underneath it) had no guard
    # at all -- a DB problem here previously surfaced as a raw traceback.
    try:
        table = get_suppliers_table()
        existing_names = {row.get("name") for row in table.all() if row.get("name")}
    except Exception as exc:
        print(f"ERROR: could not access the suppliers table: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    inserted = 0
    for raw in SUPPLIERS_SEED:
        if raw["name"] in existing_names:
            continue
        # M11: previously nothing in this loop body was guarded, and the
        # script had no explicit exit code at all -- a bad record (e.g.
        # SupplierCreate validation failure) or a mid-loop DB error would
        # either crash with a raw traceback or, if somehow swallowed
        # upstream, leave the database partially seeded with no way for
        # the operator to know which suppliers actually landed.
        try:
            validated = SupplierCreate(**raw)
            record = validated.model_dump(mode="json")
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            table.insert(record)
            inserted += 1
        except Exception as exc:
            print(
                f"ERROR: failed to insert supplier '{raw.get('name', '<unknown>')}', aborting. "
                f"{inserted} supplier(s) were committed before this failure. ({type(exc).__name__})",
                file=sys.stderr,
            )
            return 1

    total = len(table.all())
    print(f"Seeder finished: {inserted} supplier(s) inserted, {total} total in database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
