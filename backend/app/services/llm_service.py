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


def _truncate_text(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."


def _compress_segments(segments: list[Segment], limit: int, text_limit: int) -> list[Segment]:
    if len(segments) <= limit:
        return [Segment(start=s.start, end=s.end, text=_truncate_text(s.text, text_limit)) for s in segments]

    step = max(1, len(segments) // limit)
    sampled = segments[::step][:limit]
    return [Segment(start=s.start, end=s.end, text=_truncate_text(s.text, text_limit)) for s in sampled]


def _candidate_models() -> list[str]:
    candidates = [settings.lmstudio_model]
    try:
        response = requests.get(
            f"{settings.lmstudio_base_url.rstrip('/')}/models",
            timeout=20,
        )
        if response.ok:
            payload = response.json()
            ids = [item.get("id", "") for item in payload.get("data", []) if item.get("id")]
            preferred = [item for item in ids if "qwen" in item.lower()]
            ordered = preferred + ids
            candidates.extend(ordered)
    except Exception:
        logger.warning("Could not fetch LM Studio model list, using configured model only")

    return list(dict.fromkeys(candidates))


def _request_llm(model: str, segments: list[Segment], user_prompt: str | None) -> list[Segment]:
    endpoint = f"{settings.lmstudio_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "temperature": 0,
        "messages": _build_prompt(segments, user_prompt),
    }

    response = requests.post(endpoint, json=body, timeout=settings.lmstudio_timeout_seconds)
    response.raise_for_status()

    payload = response.json()
    raw_content = payload["choices"][0]["message"]["content"]
    cleaned = _strip_code_fences(raw_content)
    parsed = json.loads(cleaned)
    return _validate_segments(parsed)


def _validate_segments(payload: Any) -> list[Segment]:
    if not isinstance(payload, list):
        raise ValueError("LLM output is not a list")
    segments: list[Segment] = []
    for item in payload:
        segments.append(Segment(**item))
    return segments


def extract_highlights(segments: list[Segment], user_prompt: str | None) -> list[Segment]:
    variants = [
        segments,
        _compress_segments(segments, settings.llm_max_segments, settings.llm_segment_text_max_chars),
    ]

    for model in _candidate_models():
        for idx, segment_variant in enumerate(variants):
            try:
                logger.info(
                    "Calling LM Studio model=%s variant=%s segments=%s",
                    model,
                    "full" if idx == 0 else "compressed",
                    len(segment_variant),
                )
                return _request_llm(model, segment_variant, user_prompt)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                body = exc.response.text[:500] if exc.response is not None and exc.response.text else ""
                logger.warning("LM Studio HTTP error status=%s model=%s body=%s", status, model, body)
            except Exception:
                logger.exception("LM Studio parsing/request failed for model=%s", model)

    logger.warning("Falling back to transcript segments because LLM selection failed")
    return segments
