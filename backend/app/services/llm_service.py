from __future__ import annotations

import json
import logging
from typing import Any

import requests

from ..config import settings
from ..schemas import Segment


logger = logging.getLogger(__name__)


def _strip_code_fences(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_prompt(segments: list[Segment], user_prompt: str | None) -> list[dict[str, str]]:
    base_instruction = (
        "You are a strict video editor assistant. Return JSON only. "
        "Select highlight segments from the transcript and return a JSON array with objects "
        "{\"start\": number, \"end\": number, \"text\": string}. "
        "Never return markdown and never return explanation."
    )
    prompt_text = user_prompt.strip() if user_prompt and user_prompt.strip() else "Cut only the highlights."

    transcript_json = json.dumps([segment.model_dump() for segment in segments], ensure_ascii=True)
    user_instruction = (
        f"Task: {prompt_text}\n"
        "Keep only relevant segments. Discard unimportant content.\n"
        "Output must be valid JSON and must be parseable by json.loads.\n"
        f"Transcript segments: {transcript_json}"
    )

    return [
        {"role": "system", "content": base_instruction},
        {"role": "user", "content": user_instruction},
    ]


def _validate_segments(payload: Any) -> list[Segment]:
    if not isinstance(payload, list):
        raise ValueError("LLM output is not a list")
    segments: list[Segment] = []
    for item in payload:
        segments.append(Segment(**item))
    return segments


def extract_highlights(segments: list[Segment], user_prompt: str | None) -> list[Segment]:
    endpoint = f"{settings.lmstudio_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": settings.lmstudio_model,
        "temperature": 0,
        "messages": _build_prompt(segments, user_prompt),
    }

    response = requests.post(endpoint, json=body, timeout=settings.lmstudio_timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    raw_content = payload["choices"][0]["message"]["content"]
    cleaned = _strip_code_fences(raw_content)

    try:
        parsed = json.loads(cleaned)
        return _validate_segments(parsed)
    except Exception as exc:
        logger.exception("Could not parse LLM output. Falling back to full transcript.")
        if settings.enable_cpu_fallback:
            return segments
        raise RuntimeError("LLM did not return valid JSON") from exc
