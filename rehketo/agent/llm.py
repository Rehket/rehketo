from __future__ import annotations

from langchain_openai import ChatOpenAI

from rehketo.config import get_settings


def build_chat_model() -> ChatOpenAI:
    """Factory for the LangChain chat model pointed at Bifrost.

    Bifrost exposes an OpenAI-compatible interface; we use the Responses API
    shape so `use_responses_api=True`. The provider routing (Anthropic Claude
    Sonnet 4.6) happens inside Bifrost based on the model name.
    """
    s = get_settings()
    return ChatOpenAI(
        base_url=s.bifrost_base_url,
        api_key=s.bifrost_api_key.get_secret_value(),
        model=s.agent_model,
        use_responses_api=True,
        streaming=True,
    )
