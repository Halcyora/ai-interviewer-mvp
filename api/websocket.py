"""
Audio streaming flow:
  1. Browser opens ws://host/ws/audio/{session_id}
  2. MediaRecorder sends binary PCM chunks (16 kHz mono, every 250 ms)
  3. Server streams chunks to AWS Transcribe Streaming
  4. Partial results -> {type: "partial", text: "..."} -> browser (live captions)
  5. Final results  -> {type: "final",   text: "..."} -> appended to text area
  6. 2-second silence timeout (C2: stops Transcribe billing on dead air) ends stream
  7. Accumulated final transcript -> submit_answer() -> {type: "answer_result", data: {...}}
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from config.settings import settings

ws_router = APIRouter()


class _Handler(TranscriptResultStreamHandler):
    def __init__(self, stream, send_cb):
        super().__init__(stream)
        self._send = send_cb
        self.transcript = ""

    async def handle_transcript_event(self, event: TranscriptEvent):
        for result in event.transcript.results:
            alt_text = result.alternatives[0].transcript
            if result.is_partial:
                await self._send({"type": "partial", "text": alt_text})
            else:
                self.transcript += alt_text + " "
                await self._send({"type": "final", "text": alt_text})


@ws_router.websocket("/ws/audio/{session_id}")
async def audio_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    client = TranscribeStreamingClient(region=settings.aws_default_region)
    stream = await client.start_stream_transcription(
        language_code="en-US",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    async def send(payload: dict):
        await websocket.send_text(json.dumps(payload))

    handler = _Handler(stream.output_stream, send)
    asyncio.create_task(handler.handle_events())

    try:
        while True:
            # Timeout implements 2-second silence detection (C2: stops billing)
            chunk = await asyncio.wait_for(
                websocket.receive_bytes(),
                timeout=settings.audio_silence_timeout_sec,
            )
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await stream.input_stream.end_stream()

    final_text = handler.transcript.strip()
    if final_text:
        from db.database import AsyncSessionLocal
        from core.orchestrator import submit_answer
        async with AsyncSessionLocal() as db:
            result = await submit_answer(session_id, final_text, "AUDIO", db)
        await websocket.send_text(json.dumps({"type": "answer_result", "data": result}))

    await websocket.close()
