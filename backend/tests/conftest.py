"""Fixture integrasi backend.

Setiap sesi pytest memakai database PostgreSQL sementara yang dibuat dan
dihapus otomatis. Database pengembangan tidak pernah di-seed atau diubah.
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ftmm_compass_dev"
)
_EXPLICIT_TEST_URL = os.environ.get("FTMM_TEST_DATABASE_URL")
_SOURCE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
_CREATED_DATABASE: str | None = None
_DATABASE_ERROR: Exception | None = None


def _with_database(url: str, name: str) -> str:
    return make_url(url).set(database=name).render_as_string(hide_password=False)


def _quoted_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _admin_connection_url(url: str) -> str:
    return _with_database(url, "postgres").replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _prepare_test_database() -> None:
    global _CREATED_DATABASE, _DATABASE_ERROR
    if _EXPLICIT_TEST_URL:
        os.environ["DATABASE_URL"] = _EXPLICIT_TEST_URL
        return

    name = f"ftmm_compass_test_{os.getpid()}"
    test_url = _with_database(_SOURCE_URL, name)
    os.environ["DATABASE_URL"] = test_url

    async def recreate() -> None:
        import asyncpg

        connection = await asyncpg.connect(_admin_connection_url(_SOURCE_URL))
        try:
            await connection.execute(
                f"DROP DATABASE IF EXISTS {_quoted_identifier(name)} WITH (FORCE)"
            )
            await connection.execute(f"CREATE DATABASE {_quoted_identifier(name)}")
        finally:
            await connection.close()

    try:
        asyncio.run(recreate())
        _CREATED_DATABASE = name
    except Exception as exc:
        _DATABASE_ERROR = exc


_prepare_test_database()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

import app as app_module
from database import AsyncSessionLocal, engine, get_db
from rate_limit import limiter
from scripts.seed import seed_data


SEEDED_STUDENT = ("mahasiswa.testing@ftmm.unair.ac.id", "Mahasiswa2026!")
SEEDED_ADMIN = ("admin@ftmm.unair.ac.id", "AdminFTMM2026!")
SEEDED_PJ = ("dwi.rantini@ftmm.unair.ac.id", "PjProdi2026!")
SEEDED_LECTURER = SEEDED_PJ


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")


async def _seed_database() -> None:
    from scripts.seed_full_catalog import seed as seed_catalog

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await seed_catalog(session)
    await seed_data()


@pytest.fixture(scope="session", autouse=True)
def seeded_database():
    if _DATABASE_ERROR is not None:
        pytest.fail(
            "PostgreSQL tidak tersedia untuk database tes sementara: "
            f"{_DATABASE_ERROR}. Jalankan `make db-up`."
        )
    _run_migrations()
    asyncio.run(_seed_database())


@pytest.fixture(scope="session")
def client(seeded_database):
    with TestClient(app_module.app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolated_db(client):
    async def begin():
        connection = await engine.connect()
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        return connection, transaction, session

    connection, transaction, session = client.portal.call(begin)

    async def override_get_db():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    app_module.app.dependency_overrides[get_db] = override_get_db
    try:
        yield connection, transaction, session
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)

        async def end():
            await session.close()
            await transaction.rollback()
            await connection.close()

        client.portal.call(end)


@pytest.fixture
def db_session(isolated_db):
    """Sesi transaksional yang sama dipakai endpoint lewat dependency override."""
    yield isolated_db[2]



def _login(client: TestClient, credentials: tuple[str, str]) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def student_token(client) -> str:
    return _login(client, SEEDED_STUDENT)


@pytest.fixture(scope="session")
def admin_token(client) -> str:
    return _login(client, SEEDED_ADMIN)


@pytest.fixture(scope="session")
def lecturer_token(client) -> str:
    return _login(client, SEEDED_LECTURER)


@pytest.fixture
def student_headers(student_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {student_token}"}


@pytest.fixture
def admin_headers(client) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": SEEDED_ADMIN[0], "password": SEEDED_ADMIN[1]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def lecturer_headers(lecturer_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {lecturer_token}"}


@pytest.fixture(scope="session")
def pj_token(client) -> str:
    return _login(client, SEEDED_PJ)


@pytest.fixture
def pj_headers(pj_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {pj_token}"}


def pytest_sessionfinish(session, exitstatus):
    if _CREATED_DATABASE is None:
        return

    async def drop() -> None:
        import asyncpg

        await engine.dispose()
        connection = await asyncpg.connect(_admin_connection_url(_SOURCE_URL))
        try:
            await connection.execute(
                f"DROP DATABASE IF EXISTS {_quoted_identifier(_CREATED_DATABASE)} "
                "WITH (FORCE)"
            )
        finally:
            await connection.close()

    try:
        asyncio.run(drop())
    except Exception as exc:
        print(f"[WARN] Gagal menghapus database tes {_CREATED_DATABASE}: {exc}")
