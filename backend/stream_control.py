"""Batas koneksi SSE dan metrik yang diekspos lewat probe kesehatan."""

import asyncio
import time


class StreamTracker:
    def __init__(self, max_connections: int = 8, max_queued_tokens: int = 512):
        self.max_connections = max_connections
        self.max_queued_tokens = max_queued_tokens
        self.first_token_latency_ms: float | None = None
        self.last_stream_duration_ms: float | None = None
        self._active = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            if self._active >= self.max_connections:
                return False
            if self._active == 0:
                self.first_token_latency_ms = None
            self._active += 1
            return True

    async def release(self, started_at: float) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)
            self.last_stream_duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

    def record_first_token(self, started_at: float) -> None:
        if self.first_token_latency_ms is None:
            self.first_token_latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

    def queue_full(self, queued_tokens: int) -> bool:
        return queued_tokens >= self.max_queued_tokens

    @property
    def active_connections(self) -> int:
        return self._active

    def snapshot(self) -> dict:
        return {
            "active_streams": self._active,
            "first_token_latency_ms": self.first_token_latency_ms,
            "last_stream_duration_ms": self.last_stream_duration_ms,
        }


stream_tracker = StreamTracker()
