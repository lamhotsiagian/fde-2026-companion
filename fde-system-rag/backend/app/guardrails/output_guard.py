"""L2 — Output guard, streaming-aware.

The app streams NDJSON to the Next.js UI, and full-response guards conflict
with streaming. Two tiers:

* Tier A — ``StreamGuard``: inline scan of buffered sentences as chunks
  stream (regex PII + profanity; zero model calls, zero added latency).
  On a hit it stops the stream and emits a ``guard_retract`` NDJSON event —
  the same typed-event mechanism the UI already uses for suggestion chips.
* Tier B — ``output_guard`` node: post-completion judge for grounding and
  (for slash responses) Pydantic schema validation, with bounded retries
  and a hedged-response degrade path.
"""

import json
import re
import time
from collections.abc import AsyncIterator

from langgraph.types import Command
from pydantic import BaseModel, Field, ValidationError

from app.course.schemas import CommandResponse

from .config import guard_settings
from .llm_json import as_float, json_complete, make_json_model
from .state import GuardedState, GuardVerdict
from .validators import pii_patterns

PROFANITY_RE = re.compile(r"(?i)\b(fuck|shit|bitch|asshole|cunt)\b")
_SENTENCE_END = re.compile(r"[.!?]\s")

GROUNDING_PROMPT = """You are a grounding judge. Score how well the ANSWER is
supported by the DOCS (0.0 = fabricated, 1.0 = every claim traceable to a doc
and cited). Penalize missing [doc N] citations for factual claims.

Respond with ONE JSON object and nothing else:
{{"score": 0.0, "unsupported_claims": ["..."]}}

DOCS:
{docs}

ANSWER:
{answer}"""


class Grounding(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    unsupported_claims: list[str] = Field(default_factory=list)


_judge = make_json_model(guard_settings.judge_model)


async def _grounding(docs: str, answer: str) -> Grounding:
    """JSON-mode grounding judgment with tolerant score coercion."""
    raw = await json_complete(_judge, GROUNDING_PROMPT.format(docs=docs, answer=answer))
    claims = raw.get("unsupported_claims") or []
    if not isinstance(claims, list):
        claims = [str(claims)]
    return Grounding(score=min(1.0, max(0.0, as_float(raw.get("score")))),
                     unsupported_claims=[str(c) for c in claims][:10])


class StreamGuard:
    """Tier A: sentence-buffered inline scanner for the NDJSON stream.

    Wraps the token stream in ``app/chat/routes.py``. Buffers until a
    sentence boundary, scans the sentence, and either forwards it or kills
    the stream with a retraction event the frontend switches on.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self.tripped = False

    def _scan(self, sentence: str) -> str | None:
        for pii_type, pattern in pii_patterns().items():
            if pattern.search(sentence):
                return f"pii:{pii_type}"
        if PROFANITY_RE.search(sentence):
            return "profanity"
        return None

    async def wrap(self, chunks: AsyncIterator[str]) -> AsyncIterator[str]:
        """Yield NDJSON lines; on violation emit guard_retract and stop."""
        async for content in chunks:
            self._buffer += content
            while (m := _SENTENCE_END.search(self._buffer)):
                sentence, self._buffer = (self._buffer[: m.end()],
                                          self._buffer[m.end():])
                if (reason := self._scan(sentence)):
                    self.tripped = True
                    yield json.dumps({"type": "guard_retract",
                                      "reason": reason}) + "\n"
                    return
                yield json.dumps({"type": "llm_chunk", "content": sentence}) + "\n"
        if self._buffer and not self.tripped:
            if (reason := self._scan(self._buffer)):
                yield json.dumps({"type": "guard_retract", "reason": reason}) + "\n"
                return
            yield json.dumps({"type": "llm_chunk", "content": self._buffer}) + "\n"


async def output_guard(state: GuardedState) -> Command:
    """Tier B: schema validation (slash) + grounding judgment (RAG)."""
    t0 = time.perf_counter()
    answer = state["draft_answer"]

    # Slash-command responses are structured JSON for the UI table renderer —
    # validate with the same Pydantic model the API already returns.
    if state.get("intent") == "slash":
        try:
            CommandResponse.model_validate_json(answer)
            verdict = GuardVerdict(layer="output", decision="allow",
                                   detail="command schema valid",
                                   latency_ms=(time.perf_counter() - t0) * 1000)
            return Command(goto="audit_write",
                           update={"guard_verdicts": [verdict.model_dump()]})
        except ValidationError as exc:
            verdict = GuardVerdict(layer="output", decision="block",
                                   detail=f"schema: {exc.errors()[0]['msg']}",
                                   latency_ms=(time.perf_counter() - t0) * 1000)
            return Command(goto="malformed_response",
                           update={"guard_verdicts": [verdict.model_dump()]})

    # RAG answers: grounding judgment against the screened context.
    grounding = await _grounding(state["screened_context"], answer)
    latency_ms = (time.perf_counter() - t0) * 1000

    if grounding.score < guard_settings.grounding_min:
        verdict = GuardVerdict(layer="output", decision="retry",
                               scores={"grounding": grounding.score},
                               detail=f"unsupported: {grounding.unsupported_claims[:3]}",
                               latency_ms=latency_ms)
        if state.get("retries", 0) >= guard_settings.max_retries:
            # Degrade honestly: ship the answer with an uncertainty note
            # rather than looping the GPU forever.
            return Command(goto="hedged_response",
                           update={"guard_verdicts": [verdict.model_dump()]})
        return Command(goto="generate", update={
            "retries": state.get("retries", 0) + 1,
            "feedback": "Ground every claim in the provided docs; cite doc ids.",
            "guard_verdicts": [verdict.model_dump()],
        })

    verdict = GuardVerdict(layer="output", decision="allow",
                           scores={"grounding": grounding.score},
                           detail="grounded", latency_ms=latency_ms)
    return Command(goto="audit_write",
                   update={"guard_verdicts": [verdict.model_dump()]})
