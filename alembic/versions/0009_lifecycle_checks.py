"""Add database checks for every persisted lifecycle field."""

from alembic import op
from sqlalchemy import text

from hermes_cti.db.lifecycle import (
    LIFECYCLE_FIELDS,
    RECORD_STATUS_VALUES,
    constraint_name,
)
from hermes_cti.db.models import Base

revision = "0009_lifecycle_checks"
down_revision = "0008_provenance_completion"
branch_labels = None
depends_on = None


def _constraint_exists(name: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
            {"name": name},
        ).scalar()
    )


def _check_expression(column: str, values: tuple[str, ...]) -> str:
    encoded = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column} IN ({encoded})"


def _fields() -> list[tuple[str, str, tuple[str, ...]]]:
    fields = [
        (table, column, values) for (table, column), values in LIFECYCLE_FIELDS.items()
    ]
    fields.extend(
        (
            table.name,
            "record_status",
            RECORD_STATUS_VALUES,
        )
        for table in Base.metadata.tables.values()
        if "record_status" in table.c
    )
    return fields


def upgrade() -> None:
    for table, column, values in _fields():
        name = constraint_name(table, column)
        if not _constraint_exists(name):
            op.create_check_constraint(name, table, _check_expression(column, values))


def downgrade() -> None:
    for table, column, _values in _fields():
        name = constraint_name(table, column)
        if _constraint_exists(name):
            op.drop_constraint(name, table, type_="check")
