"""Isolated WebSocket teaching app. No uranium providers or dashboard routes."""
import asyncio
from contextlib import suppress
from itertools import count
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

DIRECTORY = Path(__file__).parent


class MockMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int = Field(ge=1, strict=True)
    value: float = Field(ge=0, allow_inf_nan=False)
    data_status: Literal["mock"] = "mock"
    connection_id: UUID


def make_message(sequence: int, connection_id: UUID) -> MockMessage:
    return MockMessage(sequence=sequence, value=100.0 + ((sequence - 1) % 10) * 0.25, connection_id=connection_id)


def create_app(interval_seconds: float = 1.0) -> FastAPI:
    if interval_seconds <= 0:
        raise ValueError("Message interval must be positive")
    demo = FastAPI(title="Mock WebSocket learning example")

    @demo.get("/", include_in_schema=False)
    def client():
        return FileResponse(DIRECTORY / "client.html")

    @demo.get("/client.js", include_in_schema=False)
    def script():
        return FileResponse(DIRECTORY / "client.js", media_type="application/javascript")

    @demo.websocket("/ws/mock")
    async def mock_stream(websocket: WebSocket):
        await websocket.accept()
        connection_id = uuid4()

        async def push_messages():
            for sequence in count(1):
                message = make_message(sequence, connection_id)
                await websocket.send_json(message.model_dump(mode="json"))
                await asyncio.sleep(interval_seconds)

        producer = asyncio.create_task(push_messages())
        try:
            # No client request is needed per message. Receive only to observe
            # the client's close/disconnect while the producer pushes independently.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            producer.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await producer

    return demo


app = create_app()
