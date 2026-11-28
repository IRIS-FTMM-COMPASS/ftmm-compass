"""baseline_schema

Revision ID: d76b9c9047cc
Revises:
Create Date: 2026-10-14 20:24:45.191731

Baseline ini menerapkan `database/schema_v2_1_rc1.sql` (baseline skema) sehingga
`alembic upgrade head` pada database kosong menghasilkan skema yang sama dengan
database hasil docker-compose. Jika seluruh tabel baseline sudah ada, baseline
dilewati; jika hanya sebagian ada, migrasi gagal dengan daftar tabel yang hilang.
"""

from pathlib import Path
import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "d76b9c9047cc"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA_FILE = Path(__file__).resolve().parents[3] / "database" / "schema_v2_1_rc1.sql"


def _split_statements(sql: str) -> list[str]:
    """Pecah skrip SQL per pernyataan, menghormati blok dollar-quoted."""
    statements: list[str] = []
    buffer: list[str] = []
    dollar_tag: str | None = None
    index = 0

    while index < len(sql):
        if dollar_tag is None and sql.startswith("$", index):
            match_end = index + 1
            while match_end < len(sql) and (
                sql[match_end].isalnum() or sql[match_end] == "_"
            ):
                match_end += 1
            if match_end < len(sql) and sql[match_end] == "$":
                tag = sql[index : match_end + 1]
                if tag == "$$" or tag[1:-1].isidentifier():
                    dollar_tag = tag
                    buffer.append(tag)
                    index = match_end + 1
                    continue

        if dollar_tag is not None and sql.startswith(dollar_tag, index):
            buffer.append(dollar_tag)
            index += len(dollar_tag)
            dollar_tag = None
            continue

        char = sql[index]
        if char == ";" and dollar_tag is None:
            statement = "".join(buffer).strip()
            statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    trailing = "".join(buffer).strip()
    if trailing:
        statements.append(trailing)

    return [statement for statement in statements if statement]


def _strip_sql_comments(sql: str) -> str:
    """Buang komentar SQL tanpa menyentuh isi string atau dollar-quoted body."""
    output: list[str] = []
    index = 0
    length = len(sql)
    dollar_tag: str | None = None
    single_quote = False
    double_quote = False
    block_depth = 0

    while index < length:
        if block_depth:
            if sql.startswith("/*", index):
                block_depth += 1
                index += 2
                continue
            if sql.startswith("*/", index):
                block_depth -= 1
                index += 2
                continue
            if sql[index] == "\n":
                output.append("\n")
            index += 1
            continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, index):
                output.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
                continue
            output.append(sql[index])
            index += 1
            continue

        if single_quote:
            output.append(sql[index])
            if sql[index] == "'":
                if index + 1 < length and sql[index + 1] == "'":
                    output.append("'")
                    index += 2
                    continue
                single_quote = False
            index += 1
            continue

        if double_quote:
            output.append(sql[index])
            if sql[index] == '"':
                if index + 1 < length and sql[index + 1] == '"':
                    output.append('"')
                    index += 2
                    continue
                double_quote = False
            index += 1
            continue

        if sql.startswith("--", index):
            newline = sql.find("\n", index)
            if newline == -1:
                break
            output.append("\n")
            index = newline + 1
            continue

        if sql.startswith("/*", index):
            block_depth = 1
            index += 2
            continue

        if sql[index] == "'":
            single_quote = True
            output.append(sql[index])
            index += 1
            continue

        if sql[index] == '"':
            double_quote = True
            output.append(sql[index])
            index += 1
            continue

        if sql[index] == "$":
            match = re.match(r"\$\$|\$[A-Za-z_][A-Za-z0-9_]*\$", sql[index:])
            if match:
                dollar_tag = match.group(0)
                output.append(dollar_tag)
                index += len(dollar_tag)
                continue

        output.append(sql[index])
        index += 1

    if block_depth:
        raise ValueError("Unterminated block comment in baseline schema")
    if dollar_tag is not None:
        raise ValueError("Unterminated dollar-quoted block in baseline schema")
    if single_quote or double_quote:
        raise ValueError("Unterminated quoted string in baseline schema")
    return "".join(output)


def _table_names(sql: str) -> set[str]:
    return {
        match.lower()
        for match in re.findall(
            r"^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            sql,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    }


def _baseline_action(expected: set[str], existing: set[str]) -> str:
    if not existing:
        return "apply"
    if existing == expected:
        return "skip"
    missing = sorted(expected - existing)
    raise RuntimeError(
        "Baseline schema is partially initialized; missing tables: "
        + ", ".join(missing)
        + ". Reset the database and run `alembic upgrade head`."
    )


def upgrade() -> None:
    bind = op.get_bind()
    raw_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    sql = _strip_sql_comments(raw_sql)
    expected = _table_names(sql)
    if not expected:
        raise RuntimeError("No CREATE TABLE statements found in baseline schema")

    existing = set(
        bind.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
    )
    action = _baseline_action(expected, existing & expected)
    if action == "skip":
        return

    for statement in _split_statements(sql):
        if statement.upper() in ("BEGIN", "COMMIT"):
            continue
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    """Baseline tidak dibalik; gunakan database baru untuk reset skema."""
