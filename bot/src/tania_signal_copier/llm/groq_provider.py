"""Groq LLM provider implementation."""

from groq import AsyncGroq

from tania_signal_copier.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    """LLM provider using Groq's API.

    Reads GROQ_API_KEY from environment automatically.
    """

    def __init__(self, model: str = "openai/gpt-oss-20b", max_tokens: int = 8192) -> None:
        """Initialize Groq provider.

        Args:
            model: The model to use (default: openai/gpt-oss-20b)
            max_tokens: Maximum completion tokens (default: 8192)
        """
        self.client = AsyncGroq()
        self.model = model
        self.max_tokens = max_tokens

    async def query(self, system_prompt: str, user_message: str) -> str:
        """Query Groq AI and get the response text.

        Args:
            system_prompt: The system prompt with instructions
            user_message: The user message to analyze

        Returns:
            The raw response text from Groq
        """
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=1,
            max_completion_tokens=self.max_tokens,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
        )

        result_text = ""
        async for chunk in completion:
            content = chunk.choices[0].delta.content
            if content:
                result_text += content

        return result_text.strip()
