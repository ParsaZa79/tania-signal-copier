"""Factory function for creating LLM providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tania_signal_copier.llm.base import LLMProvider
from tania_signal_copier.llm.cerebras_provider import CerebrasProvider
from tania_signal_copier.llm.groq_provider import GroqProvider

if TYPE_CHECKING:
    from tania_signal_copier.config import LLMConfig


def create_llm_provider(llm_config: LLMConfig) -> LLMProvider:
    """Create an LLM provider based on configuration.

    Args:
        llm_config: LLM configuration specifying provider and settings

    Returns:
        An LLM provider instance

    Raises:
        ValueError: If provider is not recognized
    """
    if llm_config.provider == "groq":
        return GroqProvider(
            model=llm_config.groq_model,
            max_tokens=llm_config.max_tokens,
        )
    elif llm_config.provider == "cerebras":
        return CerebrasProvider(
            model=llm_config.cerebras_model,
            max_tokens=llm_config.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {llm_config.provider}")
