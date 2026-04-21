from __future__ import annotations

from langchain_openai import ChatOpenAI

from rehketo.config import get_settings


def build_chat_model() -> ChatOpenAI:
    """Factory for the LangChain chat model pointed at Bifrost.

    Bifrost exposes an OpenAI-compatible interface; we hit the Chat Completions
    endpoint (`/v1/chat/completions`) because Bifrost's Anthropic-to-Responses-API
    translation currently returns a malformed `response.completed` event
    (`response.output` is `None`), which breaks LangChain's Responses streaming
    parser. Chat Completions is Bifrost's most-exercised translation path and
    works reliably for Claude Sonnet 4.6.

    Reopen the Responses path (`use_responses_api=True`) once Bifrost's
    translation emits a populated `output` array on stream completion, or when
    we point at a provider that speaks Responses natively (OpenAI).
    """
    s = get_settings()
    return ChatOpenAI(
        base_url=s.bifrost_base_url,
        api_key=s.bifrost_api_key.get_secret_value(),
        model=s.agent_model,
        use_responses_api=False,
        streaming=True,
    )
