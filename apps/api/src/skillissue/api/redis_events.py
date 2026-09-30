"""Redis Pub/Sub for scan SSE events."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import redis.asyncio as redis
from skillissue.config import get_settings


async def publish_scan_event(scan_id: str, event: dict) -> None:
    """Publish an event to the scan's Redis channel."""
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        channel = f"scan:{scan_id}:events"
        await client.publish(channel, json.dumps(event))
    except Exception:
        pass
    finally:
        await client.aclose()


async def subscribe_scan_events(scan_id: str) -> AsyncGenerator[dict, None]:
    """Subscribe to a scan's Redis channel and yield events."""
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    channel = f"scan:{scan_id}:events"
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    yield event
                    if event.get("status") in ("complete", "failed"):
                        break
                except json.JSONDecodeError:
                    pass
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass
        await client.aclose()
