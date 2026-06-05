import os
import pytest
from unittest.mock import patch
from src.infrastructure.llm_gateway import LLMClient


def test_client_respects_env_vars():
    with patch.dict(os.environ, {
        "LLM_BASE_URL": "https://custom.api.com/v1",
        "LLM_API_KEY": "env-key",
        "LLM_MODEL": "custom-model"
    }):
        client = LLMClient()
        assert "custom.api.com" in str(client.base_url)
        assert client.model == "custom-model"


def test_client_uses_defaults_when_no_env():
    with patch.dict(os.environ, {}, clear=True):
        client = LLMClient(api_key="test-key")
        assert "api.openai.com" in str(client.base_url)
        assert client.model == "gpt-4o"


def test_client_explicit_params_override_env():
    with patch.dict(os.environ, {
        "LLM_BASE_URL": "https://env.api.com/v1",
        "LLM_MODEL": "env-model"
    }):
        client = LLMClient(base_url="https://explicit.api.com/v1", model="explicit-model", api_key="key")
        assert "explicit.api.com" in str(client.base_url)
        assert client.model == "explicit-model"
