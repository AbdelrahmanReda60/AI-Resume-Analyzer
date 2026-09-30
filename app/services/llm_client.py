"""Shared LLM transport for all AI agents.

Centralises the Gemini call so every agent gets the same guarantees:
  * the key is optional - callers fall back to rule-based paths when absent
  * a hard 15s HTTP timeout (SDK milliseconds) plus an outer wall-clock timeout
  * bounded retries on transient failures
  * markdown-fence tolerant JSON extraction
  * no secrets or prompts containing user documents are ever logged
"""

from __future__ import annotations

import json
import logging
import re
import threading

from app.config import settings

logger = logging.getLogger("ai_resume_analyzer.llm")

MODEL = "gemini-2.5-flash"
LLM_TIMEOUT_MS = 15_000          # SDK timeout (milliseconds)
HARD_TIMEOUT_SECONDS = 20        # outer wall-clock guard
MAX_ATTEMPTS = 2                 # 1 retry on transient failure


class LLMError(RuntimeError):
    """Raised when the LLM cannot produce a usable response."""


def llm_available() -> bool:
    """True when a plausible Gemini key is configured."""
    key = (settings.GEMINI_API_KEY or "").strip()
    return len(key) > 5 and not key.startswith("your_")


def _call_sdk(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=LLM_TIMEOUT_MS),
    )
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = getattr(response, "text", None)
    if not text or not str(text).strip():
        raise LLMError("Empty response from LLM")
    return str(text).strip()


def _run_with_timeout(fn, *args, timeout: float = HARD_TIMEOUT_SECONDS):
    """
    Run fn on a *daemon* thread so an abandoned (hung) call can never block
    interpreter shutdown, while still enforcing a hard wall-clock deadline.
    """
    outcome: dict = {}
    finished = threading.Event()

    def worker() -> None:
        try:
            outcome["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller thread
            outcome["error"] = exc
        finally:
            finished.set()

    threading.Thread(target=worker, name="llm-call", daemon=True).start()

    if not finished.wait(timeout):
        raise LLMError(f"LLM call timed out after {timeout}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def generate_text(prompt: str, timeout: float = HARD_TIMEOUT_SECONDS) -> str:
    """Call Gemini with timeout + retry. Raises LLMError on exhaustion."""
    if not llm_available():
        raise LLMError("GEMINI_API_KEY is not configured")

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _run_with_timeout(_call_sdk, prompt, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - any SDK/network failure falls back
            last_error = exc
            logger.warning("LLM call attempt %d failed: %s", attempt, type(exc).__name__)

    raise LLMError(str(last_error) if last_error else "LLM call failed")


def clean_json_string(raw: str) -> str:
    """Strip markdown code fences and surrounding chatter from LLM output."""
    s = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    else:
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # If the model wrapped JSON in prose, keep the outermost {...} or [...]
    if not s.startswith(("{", "[")):
        start = min((i for i in (s.find("{"), s.find("[")) if i != -1), default=-1)
        if start != -1:
            s = s[start:]
    return s.strip().rstrip("`").strip()


def extract_json(raw: str) -> dict:
    """Parse LLM output into a dict, raising LLMError when it is not valid JSON."""
    candidate = clean_json_string(raw)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # Last resort: locate the first balanced JSON object
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            raise LLMError("LLM did not return valid JSON")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM returned JSON that is not an object")
    return data


def generate_json(prompt: str, timeout: float = HARD_TIMEOUT_SECONDS) -> dict:
    """Call Gemini and parse the reply as a JSON object (with one retry)."""
    try:
        return extract_json(generate_text(prompt, timeout=timeout))
    except LLMError:
        # One extra attempt specifically for malformed JSON output
        return extract_json(generate_text(prompt, timeout=timeout))
