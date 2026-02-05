"""Base protocol for LLM providers."""

from typing import Protocol


class LLMProvider(Protocol):
    """Protocol defining the interface for LLM providers."""

    async def query(self, system_prompt: str, user_message: str) -> str:
        """Query the LLM and return the response text.

        Args:
            system_prompt: The system prompt with instructions
            user_message: The user message to analyze

        Returns:
            The raw response text from the LLM
        """
        ...
