"""Central factory for OpenAI clients with optional Langfuse tracing.

Every AI interaction in the backend is created through :func:`get_openai_client`
so that, when Langfuse is configured, all chat/embedding/audio calls are traced
in one place. When Langfuse credentials are absent (local dev, CI), the factory
returns a plain ``openai.OpenAI`` client with zero tracing and no warnings — so
behaviour is unchanged wherever Langfuse is not wired up.

Tracing is enabled when both ``LANGFUSE_PUBLIC_KEY`` and ``LANGFUSE_SECRET_KEY``
are present in the environment (``LANGFUSE_HOST`` selects the self-hosted
instance). The Langfuse drop-in wrapper reads those variables itself.
"""

from __future__ import annotations

import importlib
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import OpenAI

logger = logging.getLogger(__name__)


def langfuse_enabled() -> bool:
    """Return True when Langfuse tracing credentials are configured."""
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def get_openai_client(*, api_key: str, base_url: str | None = None) -> OpenAI:
    """Return an OpenAI client, Langfuse-wrapped when tracing is configured.

    The returned object is API-compatible with ``openai.OpenAI`` in both cases,
    so call sites are identical whether or not tracing is active.
    """
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url is not None:
        kwargs["base_url"] = base_url

    if langfuse_enabled():
        # Langfuse's drop-in client subclasses openai.OpenAI and traces every
        # request. Resolve it dynamically so this module type-checks whether or
        # not langfuse is installed (it re-exports OpenAI without an __all__).
        langfuse_openai = importlib.import_module("langfuse.openai")
        client: OpenAI = langfuse_openai.OpenAI(**kwargs)
        return client

    from openai import OpenAI as PlainOpenAI

    return PlainOpenAI(**kwargs)


def flush() -> None:
    """Flush buffered Langfuse traces.

    Langfuse sends spans asynchronously; short-lived processes (e.g. the ingest
    cron) must flush before exit or trailing traces are lost. No-op when tracing
    is disabled or the SDK is unavailable.
    """
    if not langfuse_enabled():
        return
    try:
        langfuse = importlib.import_module("langfuse")
        langfuse.get_client().flush()
    except Exception as exc:
        logger.warning("langfuse flush failed: %s", exc)
