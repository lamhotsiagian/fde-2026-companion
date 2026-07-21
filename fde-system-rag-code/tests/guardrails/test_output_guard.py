"""Unit tests for the streaming output guard (tier A) and schema tier."""

import json

import pytest

from app.course.schemas import CommandResponse
from app.guardrails.output_guard import StreamGuard


async def _stream(*chunks: str):
    for c in chunks:
        yield c


@pytest.mark.asyncio
class TestStreamGuard:
    async def test_clean_stream_passes_through(self):
        guard = StreamGuard()
        events = [json.loads(line) async for line in
                  guard.wrap(_stream("NDCG rewards ranking. ", "HR@10 counts hits."))]
        assert all(e["type"] == "llm_chunk" for e in events)
        assert not guard.tripped

    async def test_pii_mid_stream_retracts(self):
        guard = StreamGuard()
        events = [json.loads(line) async for line in
                  guard.wrap(_stream("Email alice@example.com for help. more text"))]
        assert events[-1]["type"] == "guard_retract"
        assert events[-1]["reason"] == "pii:email"
        assert guard.tripped

    async def test_stream_stops_after_retraction(self):
        guard = StreamGuard()
        events = [json.loads(line) async for line in
                  guard.wrap(_stream("Call 415 555 1234 now. ",
                                     "This sentence must never be emitted."))]
        assert events[-1]["type"] == "guard_retract"
        assert not any("never be emitted" in e.get("content", "") for e in events)

    async def test_trailing_buffer_scanned(self):
        guard = StreamGuard()  # no sentence terminator at all
        events = [json.loads(line) async for line in
                  guard.wrap(_stream("ssn 078-05-1120"))]
        assert events[-1]["type"] == "guard_retract"


class TestCommandSchemaValidation:
    def test_valid_command_response_parses(self):
        raw = json.dumps({"status": "success", "message": "ok",
                          "data": {"rows": 3}})
        assert CommandResponse.model_validate_json(raw).status == "success"

    def test_malformed_response_raises(self):
        with pytest.raises(Exception):
            CommandResponse.model_validate_json('{"message": 42}')
