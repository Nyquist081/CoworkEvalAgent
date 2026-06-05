from __future__ import annotations
import os
import json
import asyncio
from typing import TypeVar, Type
from openai import AsyncOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM gateway adapter. Uses OpenAI-compatible API.

    Switch between providers by changing LLM_BASE_URL and LLM_API_KEY env vars.
    Auto-detects whether to use native structured output (OpenAI) or
    manual JSON parsing (DeepSeek / other openai-compatible providers).
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
        # Auto-detect provider: OpenAI supports beta.parse, DeepSeek and others don't
        self._supports_structured = "openai.com" in self.base_url

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

        Uses native structured output on OpenAI; manual JSON parsing on
        DeepSeek/other providers. Exponential backoff on failure.
        """
        if self._supports_structured:
            return await self._ask_openai_structured(
                system_prompt, user_prompt, response_model,
                temperature, max_retries, initial_delay,
            )
        else:
            return await self._ask_json_structured(
                system_prompt, user_prompt, response_model,
                temperature, max_retries, initial_delay,
            )

    async def _ask_openai_structured(
        self, system_prompt: str, user_prompt: str,
        response_model: Type[T], temperature: float,
        max_retries: int, initial_delay: float,
    ) -> T:
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

    async def _ask_json_structured(
        self, system_prompt: str, user_prompt: str,
        response_model: Type[T], temperature: float,
        max_retries: int, initial_delay: float,
    ) -> T:
        """JSON-mode for providers without native structured output (DeepSeek etc).
        Injects the JSON schema into the system prompt and parses the response."""
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False, indent=2)
        json_system = (
            system_prompt
            + "\n\n## Output Format\nYou MUST respond with ONLY valid JSON, no markdown, no explanation. "
            + "The JSON must conform to this schema:\n```json\n"
            + schema_json
            + "\n```"
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": json_system},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                text = completion.choices[0].message.content or ""
                # Strip markdown code fences if present
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                parsed = response_model.model_validate_json(text)
                return parsed
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        raise last_error
