"""
/inventory endpoints. Product-equivalent = Asset, inbound = AssetEntry,
outbound = AssetExit, per CONTEXT.md's Nexova mapping. URL paths keep
the README's generic /products, /orders/inbound, /orders/outbound
wording -- CONTEXT.md's own router table uses those exact paths too,
even though the underlying entities are named Asset/AssetEntry/AssetExit.

Auth: writes (POST) always require auth, per the milestone brief. GET
routes are left public here, matching this repo's existing precedent
in suppliers/router.py (list/get suppliers are public; only
create/update/delete require auth) -- Nexova's CONTEXT.md doesn't
override this with a HealthCore-style "GET also requires auth" rule.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.auth.security import get_current_user
from app.database import get_db
from app.inventory import service
from app.inventory.schemas import (
    AssetCreate,
    AssetEntryCreate,
    AssetEntryOut,
    AssetExitCreate,
    AssetExitOut,
    AssetOut,
    OrderOut,
)
from app.inventory.service import InsufficientStockError

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/products", response_model=List[AssetOut])
async def list_products(db: Session = Depends(get_db)):
    return service.list_assets_with_stock(db)


@router.post("/products", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        asset = service.create_asset(
            db, name=payload.name, sku=payload.sku, category=payload.category, office=payload.office
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An asset with sku '{payload.sku}' already exists.",
        )
    # A brand-new asset has no entries/exits yet -- current_stock is
    # always 0 at creation, per CONTEXT.md ("starts with zero stock at
    # creation and can only accumulate stock through inbound records").
    # No need to query for it.
    return AssetOut(**asset.model_dump(), current_stock=0)


@router.get("/products/{asset_id}", response_model=AssetOut)
async def get_product(asset_id: int, db: Session = Depends(get_db)):
    asset = service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    current_stock = service.compute_current_stock(db, asset_id)
    return AssetOut(**asset.model_dump(), current_stock=current_stock)


@router.post("/orders/inbound", response_model=AssetEntryOut, status_code=status.HTTP_201_CREATED)
async def create_inbound_order(
    payload: AssetEntryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    asset = service.get_asset(db, payload.asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    entry = service.create_asset_entry(
        db,
        asset_id=payload.asset_id,
        quantity=payload.quantity,
        supplier=payload.supplier,
        office=payload.office,
        # current_user["id"] is a TinyDB doc_id (int) throughout this
        # codebase, not a UUID string -- see auth/security.py. Cast to
        # str so user_uuid always holds a string as CONTEXT.md specifies,
        # regardless of which identifier shape auth ends up using.
        user_uuid=str(current_user["id"]),
    )
    return entry


@router.post("/orders/outbound", response_model=AssetExitOut, status_code=status.HTTP_201_CREATED)
async def create_outbound_order(
    payload: AssetExitCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        exit_record = service.create_asset_exit(
            db,
            asset_id=payload.asset_id,
            quantity=payload.quantity,
            exit_type=payload.exit_type,
            assigned_to=payload.assigned_to,
            office=payload.office,
            user_uuid=str(current_user["id"]),
        )
    except InsufficientStockError as exc:
        # Message format is dictated exactly by CONTEXT.md; built by
        # InsufficientStockError itself so it can't drift between here
        # and anywhere else that might raise it.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    return exit_record


@router.get("/orders", response_model=List[OrderOut])
async def list_orders(db: Session = Depends(get_db)):
    return service.list_orders(db)
