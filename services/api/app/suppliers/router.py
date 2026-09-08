"""
Supplier directory endpoints.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

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
async def create_supplier(payload: SupplierCreate):
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

    if country:
        results = [r for r in results if r["country"].lower() == country.lower()]
    if category:
        results = [
            r
            for r in results
            if category.lower() in [c.lower() for c in r["categories"]]
        ]

    return results


@router.get("/{supplier_id}", response_model=Supplier)
async def get_supplier(supplier_id: int):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return _row_to_supplier(doc)


@router.patch("/{supplier_id}/rate", response_model=Supplier)
async def update_rate(supplier_id: int, payload: SupplierRateUpdate):
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
async def update_status(supplier_id: int, payload: SupplierStatusUpdate):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    table.update({"status": payload.status.value}, doc_ids=[supplier_id])
    return _row_to_supplier(table.get(doc_id=supplier_id))


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(supplier_id: int):
    table = get_suppliers_table()
    doc = table.get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    table.remove(doc_ids=[supplier_id])
    return None
