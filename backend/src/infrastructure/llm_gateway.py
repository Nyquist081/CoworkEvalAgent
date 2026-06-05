from __future__ import annotations
import os
import asyncio
from typing import TypeVar, Type
from openai import AsyncOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM gateway adapter. Uses OpenAI-compatible API.
    Switch between providers by changing LLM_BASE_URL and LLM_API_KEY env vars.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    async def ask_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float = 0.3,
        max_retries: int = 3,
        initial_delay: float = 2.0,
    ) -> T:
        """Send prompt, parse response as structured Pydantic model.
        Exponential backoff: delay = initial_delay * 2^attempt on failure."""
        last_error = None
        for attempt in range(max_retries):
            try:
                completion = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=response_model,
                )
                parsed = completion.choices[0].message.parsed
                if parsed is not None:
                    return parsed
                raise ValueError("LLM returned None parsed response")
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        raise last_error
