"""Shared pytest configuration.

Runs the suite deterministically and offline: the LLM key is cleared before the
application is imported so every AI agent exercises its rule-based fallback
path. This keeps tests fast, repeatable, and free of network/API-key coupling.
"""

import os

os.environ["GEMINI_API_KEY"] = ""
