"""Cerebras LLM provider implementation."""

from typing import Any

from cerebras.cloud.sdk import AsyncCerebras

from tania_signal_copier.llm.base import LLMProvider


class CerebrasProvider(LLMProvider):
    """LLM provider using Cerebras's API.

    Reads CEREBRAS_API_KEY from environment automatically.
    """

    def __init__(self, model: str = "gpt-oss-120b", max_tokens: int = 8192) -> None:
        """Initialize Cerebras provider.

        Args:
            model: The model to use (default: gpt-oss-120b)
            max_tokens: Maximum completion tokens (default: 8192)
        """
        self.client = AsyncCerebras()
        self.model = model
        self.max_tokens = max_tokens

    async def query(self, system_prompt: str, user_message: str) -> str:
        """Query Cerebras AI and get the response text.

        Args:
            system_prompt: The system prompt with instructions
            user_message: The user message to analyze

        Returns:
            The raw response text from Cerebras
        """
        # Use type: ignore because Cerebras SDK type stubs don't properly
        # annotate the async iterator returned when stream=True
        stream: Any = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_completion_tokens=self.max_tokens,
            top_p=1,
            stream=True,
        )

        result_text = ""
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                result_text += content

        return result_text.strip()
