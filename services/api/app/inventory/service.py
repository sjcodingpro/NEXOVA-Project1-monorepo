"""
Service layer for the inventory domain -- stock computation and CRUD
against Supabase via the injected SQLModel session. Kept separate from
router.py so the business logic (especially stock computation) is
testable without spinning up FastAPI.

N+1 avoidance: every function that returns more than one row loads its
related data with a fixed, small number of queries regardless of how
many rows are returned -- never one extra query per row in a loop. See
each function's docstring for exactly how many queries it runs.
"""

from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.inventory.models import Asset, AssetEntry, AssetExit


class InsufficientStockError(Exception):
    """Carries the exact fields needed to build CONTEXT.md's required
    error message, without the router having to re-derive them."""

    def __init__(self, asset_name: str, available: int, requested: int):
        self.asset_name = asset_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock for asset '{asset_name}'. "
            f"Available: {available}, requested: {requested}."
        )


def _stock_by_asset(db: Session) -> dict[int, int]:
    """Two queries total (one aggregate SUM over entries, one over
    exits, each grouped by asset_id) -- not one query per asset. This
    is what list_assets_with_stock and list_orders both rely on to stay
    N+1-safe regardless of how many assets/orders exist."""
    entry_sums = dict(
        db.exec(
            select(AssetEntry.asset_id, func.sum(AssetEntry.quantity)).group_by(
                AssetEntry.asset_id
            )
        ).all()
    )
    exit_sums = dict(
        db.exec(
            select(AssetExit.asset_id, func.sum(AssetExit.quantity)).group_by(
                AssetExit.asset_id
            )
        ).all()
    )
    all_asset_ids = set(entry_sums) | set(exit_sums)
    return {
        asset_id: entry_sums.get(asset_id, 0) - exit_sums.get(asset_id, 0)
        for asset_id in all_asset_ids
    }


def compute_current_stock(db: Session, asset_id: int) -> int:
    """Stock for a single asset -- two small aggregate queries scoped
    to just this asset_id. Fine to call once per request (e.g. GET
    /inventory/products/{id}); not fine to call in a loop over many
    assets -- use list_assets_with_stock's batch path for that."""
    entry_sum = db.exec(
        select(func.sum(AssetEntry.quantity)).where(AssetEntry.asset_id == asset_id)
    ).one()
    exit_sum = db.exec(
        select(func.sum(AssetExit.quantity)).where(AssetExit.asset_id == asset_id)
    ).one()
    return (entry_sum or 0) - (exit_sum or 0)


def get_asset(db: Session, asset_id: int) -> Optional[Asset]:
    return db.get(Asset, asset_id)


def list_assets_with_stock(db: Session) -> list[dict]:
    """One query for all assets, plus _stock_by_asset's two aggregate
    queries -- three queries total, regardless of asset count."""
    assets = db.exec(select(Asset)).all()
    stock_by_asset = _stock_by_asset(db)
    return [
        {**asset.model_dump(), "current_stock": stock_by_asset.get(asset.id, 0)}
        for asset in assets
    ]


def create_asset(db: Session, name: str, sku: str, category: str, office: str) -> Asset:
    asset = Asset(name=name, sku=sku, category=category, office=office)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def create_asset_entry(
    db: Session, asset_id: int, quantity: int, supplier: str, office: str, user_uuid: str
) -> AssetEntry:
    entry = AssetEntry(
        asset_id=asset_id, quantity=quantity, supplier=supplier, office=office, user_uuid=user_uuid
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_asset_exit(
    db: Session,
    asset_id: int,
    quantity: int,
    exit_type: str,
    assigned_to: Optional[str],
    office: str,
    user_uuid: str,
) -> AssetExit:
    """Raises InsufficientStockError if the requested quantity exceeds
    current stock -- checked and raised *before* any write happens, per
    CONTEXT.md's explicit requirement ("Reject before writing")."""
    asset = get_asset(db, asset_id)
    if asset is None:
        raise ValueError(f"Asset {asset_id} not found.")

    available = compute_current_stock(db, asset_id)
    if quantity > available:
        raise InsufficientStockError(asset.name, available, quantity)

    exit_record = AssetExit(
        asset_id=asset_id,
        quantity=quantity,
        exit_type=exit_type,
        assigned_to=assigned_to,
        office=office,
        user_uuid=user_uuid,
    )
    db.add(exit_record)
    db.commit()
    db.refresh(exit_record)
    return exit_record


def list_orders(db: Session) -> list[dict]:
    """Three queries total regardless of order count: all entries, all
    exits, then ONE batched fetch of every asset referenced by either
    (Asset.id.in_(...)) -- not one asset lookup per order row. This is
    the exact N+1 pattern the milestone brief calls out by name."""
    entries = db.exec(select(AssetEntry)).all()
    exits = db.exec(select(AssetExit)).all()

    asset_ids = {e.asset_id for e in entries} | {e.asset_id for e in exits}
    assets = db.exec(select(Asset).where(Asset.id.in_(asset_ids))).all() if asset_ids else []
    asset_by_id = {a.id: a for a in assets}

    rows: list[dict] = []
    for e in entries:
        asset = asset_by_id.get(e.asset_id)
        rows.append({
            "order_type": "inbound",
            "id": e.id,
            "asset_id": e.asset_id,
            "asset_name": asset.name if asset else "",
            "asset_sku": asset.sku if asset else "",
            "quantity": e.quantity,
            "office": e.office,
            "created_at": e.created_at,
            "user_uuid": e.user_uuid,
            "supplier": e.supplier,
        })
    for x in exits:
        asset = asset_by_id.get(x.asset_id)
        rows.append({
            "order_type": "outbound",
            "id": x.id,
            "asset_id": x.asset_id,
            "asset_name": asset.name if asset else "",
            "asset_sku": asset.sku if asset else "",
            "quantity": x.quantity,
            "office": x.office,
            "created_at": x.created_at,
            "user_uuid": x.user_uuid,
            "exit_type": x.exit_type,
            "assigned_to": x.assigned_to,
        })

    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows
