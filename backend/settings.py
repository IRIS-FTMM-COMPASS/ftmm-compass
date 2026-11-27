"""Konfigurasi runtime backend: satu-satunya tempat membaca environment."""
import os
import secrets

from dotenv import load_dotenv

load_dotenv()  # environment shell menang atas berkas .env

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EKSTRAK_DIR = os.getenv("EKSTRAK_DIR") or os.path.join(REPO_ROOT, "Ekstrak")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ftmm_compass_dev",
)

# Port gateway; kosong/None berarti cari port bebas 8001-8050.
PORT_OVERRIDE = os.getenv("BACKEND_PORT") or os.getenv("PORT")
DEFAULT_BACKEND_PORT = 8001

AUTO_SEED = os.getenv("AUTO_SEED", "false").lower() in ("true", "1", "yes")

CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL", "http://127.0.0.1:8000").rstrip("/")
CHATBOT_TIMEOUT_SECONDS = float(os.getenv("CHATBOT_TIMEOUT_SECONDS", "45.0"))

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

_jwt_secret = os.getenv("JWT_SECRET_KEY")
if not _jwt_secret:
    if APP_ENV in ("production", "prod"):
        raise RuntimeError(
            "JWT_SECRET_KEY wajib diisi saat APP_ENV=production."
        )
    _jwt_secret = secrets.token_urlsafe(48)
JWT_SECRET_KEY = _jwt_secret
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 8 * 60
ACCESS_TOKEN_EXPIRE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60
DEFAULT_RATE_LIMIT = os.getenv("DEFAULT_RATE_LIMIT", "")

DEFAULT_CORS_ORIGINS = ("http://localhost:8443", "http://127.0.0.1:8443")


def parse_cors_origins(raw: str | None) -> tuple[list[str], bool]:
    origins = [origin.strip() for origin in (raw or "").split(",") if origin.strip()]
    resolved = origins or list(DEFAULT_CORS_ORIGINS)
    return resolved, "*" not in resolved


CORS_ORIGINS, CORS_ALLOW_CREDENTIALS = parse_cors_origins(
    os.getenv("CORS_ORIGINS")
)
