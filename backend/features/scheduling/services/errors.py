"""Typed service failures; routers decide how to render them as HTTP."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ServiceError:
    status_code: int
    code: str
    message: str
    details: list[dict[str, Any]] = field(default_factory=list)
