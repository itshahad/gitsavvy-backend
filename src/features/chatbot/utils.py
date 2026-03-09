import json
import logging
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws")


async def relay_pubsub(channel: str, ws: WebSocket, redis: Any):
    pubsub = redis.pubsub()  # type: ignore
    await pubsub.subscribe(channel)  # type: ignore
    print("API SUBSCRIBED:", channel)

    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)  # type: ignore
            if msg is None:
                continue

            payload = msg["data"]  # type: ignore
            print("API GOT:", payload)  # type: ignore

            try:
                await ws.send_text(payload)  # type: ignore
            except WebSocketDisconnect:
                print("WS DISCONNECTED while sending")
                break

            obj = json.loads(payload)  # type: ignore
            if obj.get("type") in ("done", "error"):
                print("API END:", obj.get("type"))
                break

    finally:
        await pubsub.unsubscribe(channel)  # type: ignore
        await pubsub.close()  # type: ignore
        print("API UNSUBSCRIBED:", channel)
