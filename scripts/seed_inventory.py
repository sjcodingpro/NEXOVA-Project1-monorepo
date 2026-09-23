#!/usr/bin/env python3
"""
scripts/seed_inventory.py

Seeds the Supabase inventory tables (Asset, AssetEntry, AssetExit) with
the minimum data specified in CONTEXT.md. Idempotent for assets (matched
by sku, per the unique constraint); entries/exits are seeded only if
neither table has any rows yet, to avoid duplicating them on a rerun
(unlike Asset, they have no natural unique key to dedupe against).

Usage:
    cd services/api
    uv run python ../../scripts/seed_inventory.py
"""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "services" / "api"
sys.path.insert(0, str(API_ROOT))

ASSETS = [
    {"name": "Laptop 14\" Business", "sku": "NXV-IT-001", "category": "hardware", "office": "Valencia"},
    {"name": "Laptop 14\" Business", "sku": "NXV-IT-002", "category": "hardware", "office": "Miami"},
    {"name": "Ergonomic mouse", "sku": "NXV-PER-001", "category": "peripherals", "office": "Valencia"},
    {"name": "USB-C Hub", "sku": "NXV-PER-002", "category": "peripherals", "office": "Miami"},
    {"name": "A4 paper ream", "sku": "NXV-OFF-001", "category": "office_supplies", "office": "Valencia"},
    {"name": "Leadership training workbook", "sku": "NXV-TRN-001", "category": "training_materials", "office": "Valencia"},
]

# 4 entries minimum: 2 for NXV-IT-001 (10 + 5, per CONTEXT.md's own
# example) and 1 each for two other assets.
ENTRIES = [
    {"sku": "NXV-IT-001", "quantity": 10, "supplier": "TechDistrib Valencia S.L."},
    {"sku": "NXV-IT-001", "quantity": 5, "supplier": "TechDistrib Valencia S.L."},
    {"sku": "NXV-PER-001", "quantity": 20, "supplier": "TechDistrib Valencia S.L."},
    # "Office Depot Miami" is used verbatim as CONTEXT.md's example
    # supplier name; it isn't implying this delivery's receiving office
    # is Miami -- office below is NXV-OFF-001's own office (Valencia).
    {"sku": "NXV-OFF-001", "quantity": 50, "supplier": "Office Depot Miami"},
]

# 3 exits minimum: at least one allocation (assigned_to set) and one
# consumption (assigned_to null). Quantities stay under what was seeded
# above for the same asset.
EXITS = [
    {"sku": "NXV-IT-001", "quantity": 1, "exit_type": "allocation", "assigned_to": "Elena Vargas"},
    {"sku": "NXV-IT-001", "quantity": 1, "exit_type": "allocation", "assigned_to": "Marcus Chen"},
    {"sku": "NXV-OFF-001", "quantity": 10, "exit_type": "consumption", "assigned_to": None},
]

SEED_USER_UUID = "seed-script"  # placeholder -- no real TinyDB user is required to seed


def main() -> int:
    try:
        from sqlmodel import Session, select
        from app.database import engine, init_inventory_db
        from app.inventory.models import Asset, AssetEntry, AssetExit
    except ImportError as exc:
        print(
            f"ERROR: could not import services/api's app package ({exc}). "
            "Run this from services/api with its dependencies installed, "
            "e.g.: cd services/api && uv run python ../../scripts/seed_inventory.py",
            file=sys.stderr,
        )
        return 1

    try:
        init_inventory_db()
    except Exception as exc:
        print(f"ERROR: could not initialize the inventory schema in Supabase: {exc}", file=sys.stderr)
        return 1

    try:
        with Session(engine) as session:
            # --- Assets: idempotent by sku ---------------------------------
            existing_skus = {a.sku for a in session.exec(select(Asset)).all()}
            asset_by_sku: dict[str, Asset] = {
                a.sku: a for a in session.exec(select(Asset)).all()
            }

            assets_inserted = 0
            for raw in ASSETS:
                if raw["sku"] in existing_skus:
                    continue
                asset = Asset(**raw)
                session.add(asset)
                session.flush()  # populate asset.id without committing yet
                asset_by_sku[asset.sku] = asset
                assets_inserted += 1

            # --- Entries/exits: only seed if neither table has data yet ----
            has_any_entries = session.exec(select(AssetEntry)).first() is not None
            has_any_exits = session.exec(select(AssetExit)).first() is not None

            entries_inserted = 0
            exits_inserted = 0

            if not has_any_entries and not has_any_exits:
                for raw in ENTRIES:
                    asset = asset_by_sku.get(raw["sku"])
                    if asset is None:
                        print(f"WARNING: skipping entry for unknown sku {raw['sku']}", file=sys.stderr)
                        continue
                    session.add(AssetEntry(
                        asset_id=asset.id,
                        quantity=raw["quantity"],
                        supplier=raw["supplier"],
                        office=asset.office,
                        user_uuid=SEED_USER_UUID,
                    ))
                    entries_inserted += 1

                for raw in EXITS:
                    asset = asset_by_sku.get(raw["sku"])
                    if asset is None:
                        print(f"WARNING: skipping exit for unknown sku {raw['sku']}", file=sys.stderr)
                        continue
                    session.add(AssetExit(
                        asset_id=asset.id,
                        quantity=raw["quantity"],
                        exit_type=raw["exit_type"],
                        assigned_to=raw["assigned_to"],
                        office=asset.office,
                        user_uuid=SEED_USER_UUID,
                    ))
                    exits_inserted += 1
            else:
                print("Entries/exits already present -- skipping (assets are still checked/inserted above).")

            session.commit()
    except Exception as exc:
        print(f"ERROR: seeding failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Seed complete: {assets_inserted} asset(s), {entries_inserted} entr(y/ies), "
        f"{exits_inserted} exit(s) inserted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
