from __future__ import annotations

import pytest

from news_dashboard.ai_client import flush, get_openai_client, langfuse_enabled

_LANGFUSE_VARS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")


@pytest.fixture
def _no_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _LANGFUSE_VARS:
        monkeypatch.delenv(var, raising=False)


def test_langfuse_enabled_requires_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    assert langfuse_enabled() is False

    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    assert langfuse_enabled() is True


@pytest.mark.usefixtures("_no_langfuse")
def test_returns_plain_openai_client_when_tracing_disabled() -> None:
    from openai import OpenAI

    client = get_openai_client(api_key="test-key")

    # Plain SDK client, not the Langfuse subclass.
    assert type(client) is OpenAI
    assert client.api_key == "test-key"


@pytest.mark.usefixtures("_no_langfuse")
def test_base_url_is_forwarded() -> None:
    client = get_openai_client(api_key="test-key", base_url="http://gateway:9130/v1")

    assert str(client.base_url).rstrip("/") == "http://gateway:9130/v1"


def test_returns_langfuse_client_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse:3000")

    client = get_openai_client(api_key="test-key")

    # Langfuse traces by wrapping the OpenAI SDK methods (wrapt), rather than
    # subclassing — a wrapt wrapper exposes the original via __wrapped__.
    assert hasattr(client.chat.completions.create, "__wrapped__")


@pytest.mark.usefixtures("_no_langfuse")
def test_flush_is_noop_without_credentials() -> None:
    # Must not raise when tracing is disabled.
    flush()
