"""
Service layer for profiles -- pure functions against TinyDB, no
FastAPI/HTTP concerns here.
"""

from typing import Optional

from app.database import get_profiles_table


def create_profile(user_id: int, name: Optional[str], phone: Optional[str], address: Optional[str]) -> dict:
    table = get_profiles_table()
    record = {"user_id": user_id, "name": name, "phone": phone, "address": address}
    doc_id = table.insert(record)
    result = dict(table.get(doc_id=doc_id))
    result["id"] = doc_id
    return result


def get_profile_by_user_id(user_id: int) -> Optional[dict]:
    table = get_profiles_table()
    for doc in table.all():
        if doc.get("user_id") == user_id:
            result = dict(doc)
            result["id"] = doc.doc_id
            return result
    return None


def update_profile(user_id: int, name=None, phone=None, address=None) -> Optional[dict]:
    existing = get_profile_by_user_id(user_id)
    if existing is None:
        return None

    table = get_profiles_table()
    updates = {}
    if name is not None:
        updates["name"] = name
    if phone is not None:
        updates["phone"] = phone
    if address is not None:
        updates["address"] = address

    if updates:
        table.update(updates, doc_ids=[existing["id"]])

    result = dict(table.get(doc_id=existing["id"]))
    result["id"] = existing["id"]
    return result


def delete_profile_by_user_id(user_id: int) -> None:
    existing = get_profile_by_user_id(user_id)
    if existing is not None:
        table = get_profiles_table()
        table.remove(doc_ids=[existing["id"]])
