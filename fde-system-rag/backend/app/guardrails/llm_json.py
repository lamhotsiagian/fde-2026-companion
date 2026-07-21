"""Robust JSON completion for local Ollama models.

``ChatOllama.with_structured_output()`` is unreliable on small local models:
they echo the schema back (``{"injection": {"description": ..., "value": false}}``),
wrap scalars in ``{"value": x}``, emit "true"/"false" as strings, or add prose
around the JSON. Rather than trust it, every guard classifier/judge uses this
module: force Ollama's native JSON mode (``format="json"``) and parse
tolerantly -- unwrap value-objects, coerce bool/float/str from whatever the
model produced, and ignore extra keys.

This keeps the guards working on a 1B model, which is the whole point of using
a small, cheap classifier at the input tier.
"""

import json
import re
from typing import Any

from langchain_ollama import ChatOllama

from app.config import settings


def make_json_model(model_name: str) -> ChatOllama:
    """A deterministic ChatOllama pinned to JSON output mode."""
    return ChatOllama(
        model=model_name, base_url=settings.model_base_url,
        temperature=0, format="json",
    )


def _unwrap(v: Any) -> Any:
    """Small models sometimes return {"description": ..., "value": x} or
    {"value": x} for a scalar field. Pull the scalar back out."""
    if isinstance(v, dict):
        for key in ("value", "val", "answer", "result", "label", "score"):
            if key in v:
                return v[key]
    return v


def as_bool(v: Any, default: bool = False) -> bool:
    v = _unwrap(v)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1", "y", "t")
    return default


def as_float(v: Any, default: float = 0.0) -> float:
    v = _unwrap(v)
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:\.\d+)?", v)
        return float(m.group()) if m else default
    return default


def as_str(v: Any, default: str = "") -> str:
    v = _unwrap(v)
    return str(v).strip() if v is not None else default


async def json_complete(model: ChatOllama, prompt: str) -> dict:
    """Invoke the model and return a parsed dict, tolerant of stray prose."""
    resp = await model.ainvoke(prompt)
    text = getattr(resp, "content", resp)
    if not isinstance(text, str):
        text = str(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)  # salvage an embedded object
        if not m:
            raise
        data = json.loads(m.group())
    return data if isinstance(data, dict) else {}
