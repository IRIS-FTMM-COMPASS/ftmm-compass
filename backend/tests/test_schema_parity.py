"""Schema parity between ORM metadata and the migrated PostgreSQL database."""

from sqlalchemy import text

import models  # noqa: F401
from database import AsyncSessionLocal, Base

CORE_SCHEMA_TABLES = {
    "source_documents",
    "curriculum_cohort_rules",
    "chat_sessions",
    "chat_messages",
    "grade_scale",
}


def test_orm_columns_match_migrated_database(client):
    async def read_schema():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT table_name, column_name, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public'"
                )
            )
            schema: dict[str, dict[str, bool]] = {}
            for table_name, column_name, is_nullable in result:
                schema.setdefault(table_name, {})[column_name] = is_nullable == "YES"
            return schema

    schema = client.portal.call(read_schema)

    missing_tables = sorted(CORE_SCHEMA_TABLES - schema.keys())
    assert not missing_tables, f"Canonical tables missing from database: {missing_tables}"

    for table in Base.metadata.sorted_tables:
        assert table.name in schema, f"Model table {table.name} is missing from database"
        database_columns = schema[table.name]
        model_columns = {column.name: column.nullable for column in table.columns}

        missing_columns = sorted(model_columns.keys() - database_columns.keys())
        assert not missing_columns, (
            f"Model columns missing from database table {table.name}: {missing_columns}"
        )

        nullability_mismatches = {
            name: (model_columns[name], database_columns[name])
            for name in model_columns
            if model_columns[name] != database_columns[name]
        }
        assert not nullability_mismatches, (
            f"Nullability mismatch in {table.name}: {nullability_mismatches}"
        )
