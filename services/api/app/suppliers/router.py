"""
Supplier directory endpoints.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import ValidationError

from app.auth.security import get_current_user
from app.database import get_suppliers_table
from app.suppliers.models import (
    Supplier,
    SupplierCreate,
    SupplierRateUpdate,
    SupplierStatusUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _row_to_supplier(doc) -> dict:
    data = dict(doc)
    data["id"] = doc.doc_id
    return data


@router.post("", response_model=Supplier, status_code=201)
async def create_supplier(payload: SupplierCreate, current_user: dict = Depends(get_current_user)):
    table = get_suppliers_table()
    record = payload.model_dump(mode="json")
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc_id = table.insert(record)
    return _row_to_supplier(table.get(doc_id=doc_id))


@router.get("", response_model=List[Supplier])
async def list_suppliers(
    country: Optional[str] = None, category: Optional[str] = None
):
    table = get_suppliers_table()
    results = [_row_to_supplier(r) for r in table.all()]

    # New finding (same class as M13 in incidents/router.py, found during
    # a repo-wide sweep): a legacy/hand-edited row missing "country" or
    # "categories" entirely raised an unhandled KeyError here, 500-ing
    # the whole list for every filter, not just for that one row.
    if country:
        results = [r for r in results if (r.get("country") or "").lower() == country.lower()]
    if category:
        results = [
            r
            for r in results
            if category.lower() in [c.lower() for c in r.get("categories", [])]
        ]

    # A malformed row surviving the filters above (or present at all,
    # when no filter is applied) would otherwise 500 the *entire*
    # response here anyway, via FastAPI's response_model=List[Supplier]
    # validation -- the filter fix alone isn't sufficient. Validate
    # per-row and skip anything that doesn't fit the model, same
    # approach as M13.
    validated: List[Supplier] = []
    for r in results:
        try:
            validated.append(Supplier(**r))
        except ValidationError:
            continue
    return validated


@router.get("/{supplier_id}", response_model=Supplier)
async def get_supplier(supplier_id: int):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return _row_to_supplier(doc)


@router.patch("/{supplier_id}/rate", response_model=Supplier)
async def update_rate(supplier_id: int, payload: SupplierRateUpdate, current_user: dict = Depends(get_current_user)):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    updated_at = datetime.now(timezone.utc).isoformat()
    table.update(
        {"monthly_rate": payload.monthly_rate, "updated_at": updated_at},
        doc_ids=[supplier_id],
    )
    return _row_to_supplier(table.get(doc_id=supplier_id))


@router.patch("/{supplier_id}/status", response_model=Supplier)
async def update_status(supplier_id: int, payload: SupplierStatusUpdate, current_user: dict = Depends(get_current_user)):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    table.update({"status": payload.status.value}, doc_ids=[supplier_id])
    return _row_to_supplier(table.get(doc_id=supplier_id))


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(supplier_id: int, current_user: dict = Depends(get_current_user)):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    table.remove(doc_ids=[supplier_id])
    return None
