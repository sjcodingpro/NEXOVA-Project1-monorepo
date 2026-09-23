"""
Tests for the inventory domain. Business logic, not HTTP plumbing --
per the "test what the endpoint decides, not how it responds" principle
this repo has used throughout.
"""

from sqlalchemy import event

from app.inventory.models import Asset, AssetEntry, AssetExit
from app.inventory import service


def _auth(make_user, auth_headers):
    user_id, _, _ = make_user()
    return auth_headers(user_id)


def _make_asset(inventory_client, headers, sku="NXV-IT-001", office="Valencia"):
    r = inventory_client.post(
        "/inventory/products",
        json={"name": "Laptop 14\" Business", "sku": sku, "category": "hardware", "office": office},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


class TestAssetCreation:
    def test_new_asset_starts_at_zero_stock(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        assert asset["current_stock"] == 0

    def test_duplicate_sku_is_rejected_with_400_not_500(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        _make_asset(inventory_client, headers, sku="NXV-IT-001")

        response = inventory_client.post(
            "/inventory/products",
            json={"name": "Different name", "sku": "NXV-IT-001", "category": "hardware", "office": "Miami"},
            headers=headers,
        )

        assert response.status_code == 400

    def test_unauthenticated_create_is_rejected(self, inventory_client):
        response = inventory_client.post(
            "/inventory/products",
            json={"name": "X", "sku": "NXV-X-001", "category": "hardware", "office": "Valencia"},
        )
        assert response.status_code == 401

    def test_unknown_category_is_rejected(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        response = inventory_client.post(
            "/inventory/products",
            json={"name": "X", "sku": "NXV-X-002", "category": "not_a_real_category", "office": "Valencia"},
            headers=headers,
        )
        assert response.status_code == 422


class TestStockComputation:
    def test_stock_is_net_of_entries_and_exits(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        asset_id = asset["id"]

        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset_id, "quantity": 10, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
            headers=headers,
        )
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset_id, "quantity": 5, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
            headers=headers,
        )
        inventory_client.post(
            "/inventory/orders/outbound",
            json={"asset_id": asset_id, "quantity": 3, "exit_type": "consumption", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.get(f"/inventory/products/{asset_id}")

        assert response.json()["current_stock"] == 12  # 10 + 5 - 3

    def test_products_list_reflects_the_same_computation_as_single_product(
        self, inventory_client, make_user, auth_headers
    ):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 7, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        list_response = inventory_client.get("/inventory/products")
        single_response = inventory_client.get(f"/inventory/products/{asset['id']}")

        listed = next(a for a in list_response.json() if a["id"] == asset["id"])
        assert listed["current_stock"] == single_response.json()["current_stock"] == 7


class TestInsufficientStock:
    def test_exit_exceeding_available_stock_is_rejected_with_exact_message(
        self, inventory_client, make_user, auth_headers
    ):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.post(
            "/inventory/orders/outbound",
            json={"asset_id": asset["id"], "quantity": 10, "exit_type": "consumption", "office": "Valencia"},
            headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            f"Insufficient stock for asset '{asset['name']}'. Available: 5, requested: 10."
        )

    def test_rejected_exit_does_not_get_persisted(self, inventory_client, make_user, auth_headers, db_session):
        """The rejection happens *before* the write -- confirmed by
        checking no AssetExit row exists afterward, not just that the
        HTTP response was a 400."""
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 2, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        inventory_client.post(
            "/inventory/orders/outbound",
            json={"asset_id": asset["id"], "quantity": 100, "exit_type": "consumption", "office": "Valencia"},
            headers=headers,
        )

        from sqlmodel import select
        remaining = db_session.exec(select(AssetExit)).all()
        assert len(remaining) == 0

    def test_exit_for_exactly_the_available_amount_succeeds(self, inventory_client, make_user, auth_headers):
        """Edge case: the boundary itself (requesting exactly what's
        available, not one more) must succeed, not be caught by an
        off-by-one in the comparison."""
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.post(
            "/inventory/orders/outbound",
            json={"asset_id": asset["id"], "quantity": 5, "exit_type": "consumption", "office": "Valencia"},
            headers=headers,
        )

        assert response.status_code == 201


class TestAllocationConsumptionValidation:
    def test_allocation_without_assigned_to_is_rejected(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.post(
            "/inventory/orders/outbound",
            json={"asset_id": asset["id"], "quantity": 1, "exit_type": "allocation", "office": "Valencia"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_consumption_with_assigned_to_is_rejected(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.post(
            "/inventory/orders/outbound",
            json={
                "asset_id": asset["id"],
                "quantity": 1,
                "exit_type": "consumption",
                "assigned_to": "Jane Doe",
                "office": "Valencia",
            },
            headers=headers,
        )

        assert response.status_code == 422

    def test_allocation_with_assigned_to_succeeds(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.post(
            "/inventory/orders/outbound",
            json={
                "asset_id": asset["id"],
                "quantity": 1,
                "exit_type": "allocation",
                "assigned_to": "Jane Doe",
                "office": "Valencia",
            },
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["assigned_to"] == "Jane Doe"


class TestUserUuidTracking:
    def test_inbound_order_records_the_authenticated_users_uuid(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)

        response = inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )

        assert response.json()["user_uuid"]  # non-empty -- came from the token, not the request body

    def test_orders_list_includes_user_uuid_and_asset_data(self, inventory_client, make_user, auth_headers):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 5, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
            headers=headers,
        )

        response = inventory_client.get("/inventory/orders")

        row = response.json()[0]
        assert row["user_uuid"]
        assert row["asset_name"] == asset["name"]
        assert row["asset_sku"] == asset["sku"]
        assert row["order_type"] == "inbound"


class TestForeignKeyEnforcement:
    def test_asset_entry_with_a_nonexistent_asset_id_is_rejected_at_the_database_level(self, db_session):
        """Bypasses the router's own application-level existence check
        entirely -- this inserts directly through the ORM session to
        confirm the FK constraint itself is enforced by the database,
        not just by app code that happens to check first."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        orphan_entry = AssetEntry(
            asset_id=999999, quantity=1, supplier="X", office="Valencia", user_uuid="1"
        )
        db_session.add(orphan_entry)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestNPlusOneAvoidance:
    """Directly counts SQL statements executed -- asserting query
    *count* stays flat while row count grows is what actually proves
    the N+1 pattern was avoided, per the milestone's explicit warning
    about this."""

    def _count_queries(self, engine, fn):
        count = {"n": 0}

        def _on_execute(*args, **kwargs):
            count["n"] += 1

        event.listen(engine, "before_cursor_execute", _on_execute)
        try:
            fn()
        finally:
            event.remove(engine, "before_cursor_execute", _on_execute)
        return count["n"]

    def test_listing_products_uses_a_fixed_query_count_regardless_of_asset_count(
        self, inventory_client, make_user, auth_headers, inventory_engine
    ):
        headers = _auth(make_user, auth_headers)
        for i in range(8):
            _make_asset(inventory_client, headers, sku=f"NXV-TEST-{i:03d}")

        queries_for_8 = self._count_queries(inventory_engine, lambda: inventory_client.get("/inventory/products"))

        _make_asset(inventory_client, headers, sku="NXV-TEST-EXTRA")
        queries_for_9 = self._count_queries(inventory_engine, lambda: inventory_client.get("/inventory/products"))

        # If this were N+1, adding one more asset would add at least
        # one more query. It shouldn't add any.
        assert queries_for_9 == queries_for_8

    def test_listing_orders_uses_a_fixed_query_count_regardless_of_order_count(
        self, inventory_client, make_user, auth_headers, inventory_engine
    ):
        headers = _auth(make_user, auth_headers)
        asset = _make_asset(inventory_client, headers)
        for _ in range(6):
            inventory_client.post(
                "/inventory/orders/inbound",
                json={"asset_id": asset["id"], "quantity": 1, "supplier": "X", "office": "Valencia"},
                headers=headers,
            )

        queries_for_6 = self._count_queries(inventory_engine, lambda: inventory_client.get("/inventory/orders"))

        inventory_client.post(
            "/inventory/orders/inbound",
            json={"asset_id": asset["id"], "quantity": 1, "supplier": "X", "office": "Valencia"},
            headers=headers,
        )
        queries_for_7 = self._count_queries(inventory_engine, lambda: inventory_client.get("/inventory/orders"))

        assert queries_for_7 == queries_for_6
