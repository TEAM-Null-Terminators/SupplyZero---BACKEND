import asyncio
import json
import logging
from collections import deque
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Bounded per-client queues prevent slow sockets from stalling ingestion."""

    def __init__(self, queue_size: int = 256):
        self.clients: dict[WebSocket, asyncio.Queue[str]] = {}
        self.queue_size = queue_size
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> asyncio.Queue[str]:
        await websocket.accept()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self.queue_size)
        async with self._lock:
            self.clients[websocket] = queue
        return queue

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.clients.pop(websocket, None)

    async def publish(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str, separators=(",", ":"))
        async with self._lock:
            clients = list(self.clients.items())
        for websocket, queue in clients:
            try:
                if queue.full():
                    queue.get_nowait()  # discard stale update; never block the producer
                queue.put_nowait(payload)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                logger.warning("websocket_queue_overflow")


manager = WebSocketManager()


async def websocket_sender(websocket: WebSocket, queue: asyncio.Queue[str]) -> None:
    try:
        while True:
            await websocket.send_text(await queue.get())
    except Exception:
        await manager.disconnect(websocket)
