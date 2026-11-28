"""Regression tests for the baseline schema migration parser."""

import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "d76b9c9047cc_baseline_schema.py"
)
SPEC = importlib.util.spec_from_file_location("baseline_schema_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


def test_strip_comments_preserves_dollar_quoted_body_and_strings():
    sql = """-- outside comment
CREATE OR REPLACE FUNCTION sample()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    -- comment inside body
    PERFORM '--not a comment';
END;
$$;
/* trailing block comment */
"""
    cleaned = baseline._strip_sql_comments(sql)
    assert "-- outside comment" not in cleaned
    assert "/* trailing block comment */" not in cleaned
    assert "-- comment inside body" in cleaned
    assert "'--not a comment'" in cleaned

    statements = baseline._split_statements(cleaned)
    assert len(statements) == 1
    assert statements[0].startswith("CREATE OR REPLACE FUNCTION sample()")
    assert statements[0].endswith("$$")


def test_table_names_extracts_baseline_tables():
    sql = "CREATE TABLE users (id int);\nCREATE TABLE IF NOT EXISTS courses (id int);"
    assert baseline._table_names(sql) == {"users", "courses"}


def test_baseline_action_rejects_partial_schema():
    assert baseline._baseline_action({"users", "courses"}, set()) == "apply"
    assert baseline._baseline_action({"users", "courses"}, {"users", "courses"}) == "skip"
    with pytest.raises(RuntimeError, match="partially initialized.*courses"):
        baseline._baseline_action({"users", "courses"}, {"users"})
