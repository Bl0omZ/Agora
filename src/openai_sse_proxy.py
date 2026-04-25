"""OpenAI-compatible SSE proxy adapter for non-standard local gateways.

Supports both non-streaming callers (returns ChatCompletion) and streaming
callers (returns a single-chunk async iterator yielding one ChatCompletionChunk
that contains the full aggregated content).

The streaming path is required by Semantic Kernel's GroupChatOrchestration /
``invoke_stream`` pipeline, which always forces ``stream=True`` on the
underlying OpenAI client. Since the local SSE gateway only speaks streaming
upstream, we always go SSE upstream, aggregate to a complete ChatCompletion,
and then either return it directly (non-stream caller) or wrap it in a single
``ChatCompletionChunk`` exposed via a duck-typed async iterator (stream caller).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

logger = logging.getLogger(__name__)


class _PseudoAsyncStream(AsyncStream[ChatCompletionChunk]):
    """Single-chunk async iterator compatible with SK's streaming consumer.

    SK's ``_inner_get_streaming_chat_message_contents`` does:
        if not isinstance(response, AsyncStream): raise ServiceInvalidResponseError
        async for chunk in response: ...
        assert isinstance(chunk, ChatCompletionChunk)

    The ``isinstance(response, AsyncStream)`` check is the strict gate. We
    bypass it by registering this class as a virtual subclass of
    ``openai.AsyncStream`` (see module-level ``AsyncStream.register`` call
    below). Then SK iterates and only the per-chunk type-assertion matters,
    which we satisfy by emitting real ``ChatCompletionChunk`` instances.
    """

    def __init__(self, chunks: list[ChatCompletionChunk]) -> None:
        # Do not call AsyncStream.__init__; it requires a live httpx.Response.
        # SK only needs isinstance(response, AsyncStream), async iteration, close(),
        # and a harmless usage attribute for OpenAIHandler.store_usage().
        self._chunks = chunks
        self._idx = 0
        self.usage = None

    def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        return self

    async def __anext__(self) -> ChatCompletionChunk:
        if self._idx >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk

    async def close(self) -> None:  # API parity with openai.AsyncStream
        return None


class _SSEProxyChatCompletions:
    """Aggregate SSE chunks from a proxy into either a ChatCompletion (non-stream)
    or a single-chunk pseudo AsyncStream (stream)."""

    def __init__(self, client: "SSEProxyAsyncOpenAI") -> None:
        self._client = client

    async def create(
        self,
        *,
        stream: bool | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> ChatCompletion | _PseudoAsyncStream:
        request_body = dict(kwargs)
        # Always upstream as SSE; the local gateway only speaks streaming.
        request_body["stream"] = True
        # ``stream_options`` is OpenAI-spec but the local gateway rejects it.
        request_body.pop("stream_options", None)
        request_body.pop("response_format", None)

        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
        }
        if self._client.api_key:
            headers["Authorization"] = f"Bearer {self._client.api_key}"
        if extra_headers:
            headers.update(extra_headers)

        response = await self._client._client.post(  # type: ignore[attr-defined]
            "/chat/completions",
            json=request_body,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()

        completion = _build_chat_completion_from_sse(
            response.text, fallback_model=request_body.get("model")
        )

        if not stream:
            return completion

        # Streaming caller: wrap the aggregated completion as a single chunk.
        chunk = _completion_to_single_chunk(completion)
        return _PseudoAsyncStream([chunk])


class _SSEProxyChat:
    """Minimal chat namespace compatible with AsyncOpenAI.chat.completions."""

    def __init__(self, client: "SSEProxyAsyncOpenAI") -> None:
        self.completions = _SSEProxyChatCompletions(client)


class SSEProxyAsyncOpenAI(AsyncOpenAI):
    """AsyncOpenAI subclass that adapts SSE-only proxies to ChatCompletion."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.chat = _SSEProxyChat(self)  # type: ignore[assignment]


def _build_chat_completion_from_sse(payload: str, fallback_model: str | None = None) -> ChatCompletion:
    """Parse SSE text payload into a standard chat completion object."""
    content_parts: list[str] = []
    response_id = "sse-proxy"
    created = int(time.time())
    model = fallback_model or "unknown"
    finish_reason: str | None = "stop"
    usage: dict[str, Any] | None = None
    service_tier: str | None = None
    system_fingerprint: str | None = None

    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue

        chunk = json.loads(data)
        response_id = chunk.get("id", response_id)
        created = int(chunk.get("created", created))
        model = chunk.get("model", model)
        service_tier = chunk.get("service_tier", service_tier)
        system_fingerprint = chunk.get("system_fingerprint", system_fingerprint)
        usage = chunk.get("usage", usage)

        choices = chunk.get("choices", [])
        if not choices:
            continue

        choice = choices[0]
        delta = choice.get("delta", {})
        delta_content = _extract_text(delta.get("content"))
        if delta_content:
            content_parts.append(delta_content)

        message_content = _extract_text((choice.get("message") or {}).get("content"))
        if message_content:
            content_parts.append(message_content)

        choice_text = _extract_text(choice.get("text"))
        if choice_text:
            content_parts.append(choice_text)

        finish_reason = choice.get("finish_reason", finish_reason)

    final_content = "".join(content_parts)
    if not final_content:
        logger.warning("SSE proxy returned no text content; falling back to empty assistant message.")

    return ChatCompletion.model_validate(
        {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "service_tier": service_tier,
            "system_fingerprint": system_fingerprint,
            "usage": usage,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish_reason or "stop",
                    "logprobs": None,
                    "message": {
                        "role": "assistant",
                        "content": final_content,
                    },
                }
            ],
        }
    )


def _extract_text(value: Any) -> str:
    """Extract assistant text from OpenAI-compatible content shapes."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_extract_text(item) for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return _extract_text(value.get("text"))
        if "content" in value:
            return _extract_text(value.get("content"))
    return ""


def _completion_to_single_chunk(completion: ChatCompletion) -> ChatCompletionChunk:
    """Wrap a complete ChatCompletion into a single ChatCompletionChunk.

    SK's streaming consumer only needs:
      - chunk.choices[*].delta.content (full text in one shot)
      - chunk.choices[*].finish_reason
      - chunk.usage (optional)
      - chunk.id / chunk.created / chunk.model

    We emit ONE chunk that contains everything, equivalent to a non-streaming
    response but presented through the streaming interface.
    """
    choice = completion.choices[0] if completion.choices else None
    content = ""
    finish_reason: str | None = "stop"
    if choice is not None:
        msg = choice.message
        # message.content is Optional[str]; coerce None to "" to satisfy delta schema
        content = msg.content or ""
        finish_reason = choice.finish_reason or "stop"

    usage_payload: dict[str, Any] | None = None
    if completion.usage is not None:
        usage_payload = completion.usage.model_dump()

    chunk_dict: dict[str, Any] = {
        "id": completion.id,
        "object": "chat.completion.chunk",
        "created": completion.created,
        "model": completion.model,
        "system_fingerprint": completion.system_fingerprint,
        "service_tier": completion.service_tier,
        "usage": usage_payload,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "logprobs": None,
                "delta": {
                    "role": "assistant",
                    "content": content,
                },
            }
        ],
    }

    return ChatCompletionChunk.model_validate(chunk_dict)
