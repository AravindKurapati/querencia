"""Resolving optional external-API credentials, local-first style.

querencia is local-first: every step that talks to an external service
(Google Places enrichment/recommendation, Anthropic prose synthesis) must
degrade to an offline fallback when no key is configured, never crash. Callers
rely on the client constructors raising ``KeyError`` -- and only ``KeyError``
-- so a single ``except KeyError`` cleanly selects the offline path.

``require_env_key`` centralizes that contract. It treats a missing env var and
a present-but-blank env var identically, because an empty
``GOOGLE_PLACES_API_KEY`` / ``ANTHROPIC_API_KEY`` (common in ``.env`` files and
CI) should fall back, not blow up inside the vendor SDK with a ``ValueError``.
Resolving the key *before* importing the (heavy, optional) vendor library also
means the no-key path never imports it at all.
"""
from __future__ import annotations

import os


def require_env_key(name: str, override: str | None = None) -> str:
    """Return a non-empty API key from ``override`` or environment ``name``.

    The value is stripped of surrounding whitespace (so a trailing newline read
    into the env var doesn't corrupt the key). Raises ``KeyError`` if neither
    source yields a non-empty value, so callers' offline fallback triggers
    uniformly for both unset and blank credentials.
    """
    value = override if override is not None else os.environ.get(name)
    if value is not None:
        value = value.strip()
    if not value:
        raise KeyError(name)
    return value
