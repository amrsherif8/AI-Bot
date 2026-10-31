"""Shared Gemini client used by the translator, document Q&A and the voice assistant."""
import os
import time

from dotenv import load_dotenv
from pathlib import Path as _P
from google import genai
from google.genai import types

load_dotenv(_P(__file__).resolve().parent / ".env", encoding="utf-8-sig")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
RETRY_CODES = {429, 500, 503, 504}     # أخطاء مؤقتة: نعيد المحاولة
FATAL_CODES = {400, 401, 403}          # مفتاح أو طلب غلط: مفيش فايدة من الإعادة
ATTEMPTS = 3
_client = None


class LLMUnavailable(Exception):
    pass


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMUnavailable("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=key)
    return _client


def chat(messages, temperature=0.2, max_tokens=1024):
    """messages: list of {"role": "system"|"user"|"assistant", "content": str}.
    Returns the reply text. Raises LLMUnavailable on any failure."""
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))

    config = types.GenerateContentConfig(
        system_instruction="\n\n".join(system_parts) or None,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    models = [MODEL_NAME] + ([FALLBACK_MODEL] if FALLBACK_MODEL and FALLBACK_MODEL != MODEL_NAME else [])
    last_error = "unknown error"
    text = ""
    for model in models:
        for attempt in range(ATTEMPTS):
            try:
                response = _get_client().models.generate_content(
                    model=model, contents=contents, config=config,
                )
                text = (response.text or "").strip()
                break
            except LLMUnavailable:
                raise
            except Exception as error:
                last_error = str(error)
                code = getattr(error, "code", None)
                if code in FATAL_CODES:
                    raise LLMUnavailable(last_error) from None
                if code in RETRY_CODES and attempt < ATTEMPTS - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break           # جرّب الموديل الاحتياطي
        if text:
            break
    if not text:
        raise LLMUnavailable(last_error)
    return text