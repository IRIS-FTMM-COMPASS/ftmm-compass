"""Konstanta bersama untuk layanan domain penjadwalan."""

from fastapi import status

UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
