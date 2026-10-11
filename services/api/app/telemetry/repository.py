from typing import Any

from sqlalchemy import Column, DateTime, MetaData, Numeric, Table, Text, insert, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import engine

# Separate MetaData: SQLModel.metadata.create_all() must never touch this
# table. It is created and indexed in Supabase (see the SQL in the PR).
_metadata = MetaData()

telemetry_events = Table(
    "telemetry_events",
    _metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("service", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("level", Text, nullable=False, server_default=text("'info'")),
    Column("value", Numeric),
    Column("message", Text),
    Column("tags", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
)


def bulk_insert_telemetry(rows: list[dict[str, Any]]) -> int:
    """Insert all rows in ONE statement and ONE transaction.

    Append-only by design: this module has no update or delete path.
    """
    if not rows:
        return 0
    with engine.begin() as conn:
        result = conn.execute(insert(telemetry_events).values(rows))
    return result.rowcount
