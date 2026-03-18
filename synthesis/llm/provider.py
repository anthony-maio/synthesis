"""
LLM provider abstraction and implementations.

Supports multiple LLM backends through a unified interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Response from an LLM"""
    content: str
    finish_reason: str
    tokens_used: Optional[int] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            prompt: The prompt to complete
            system: Optional system message
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse with generated content
        """
        pass


class ClaudeProvider(LLMProvider):
    """Claude API provider using Anthropic SDK"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key
            model: Model to use
        """
        self.api_key = api_key
        self.model = model

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic package required for Claude provider. "
                "Install with: pip install anthropic"
            )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a completion using Claude API"""
        messages = [{"role": "user", "content": prompt}]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "",
            messages=messages,
        )

        return LLMResponse(
            content=response.content[0].text,
            finish_reason=response.stop_reason or "stop",
            tokens_used=response.usage.output_tokens if hasattr(response, 'usage') else None,
        )


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for accessing multiple models"""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model to use
            base_url: OpenRouter API base URL
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/synthesis-ai/synthesis",
                "X-Title": "Synthesis AI",
            },
            timeout=120.0,
        )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a completion using OpenRouter"""
        messages = [{"role": "user", "content": prompt}]

        if system:
            messages.insert(0, {"role": "system", "content": system})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            finish_reason=data["choices"][0]["finish_reason"],
            tokens_used=data.get("usage", {}).get("completion_tokens"),
        )

    async def close(self) -> None:
        """Close the client"""
        await self.client.aclose()


class MockProvider(LLMProvider):
    """Mock provider for testing"""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        """
        Initialize mock provider.

        Args:
            responses: Dictionary mapping prompt patterns to responses
        """
        self.responses = responses or {}
        self.call_count = 0
        self.last_prompt = None

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any
    ) -> LLMResponse:
        """Return a mock response"""
        self.call_count += 1
        self.last_prompt = prompt

        # Check for pattern matches
        for pattern, response in self.responses.items():
            if pattern in prompt:
                return LLMResponse(
                    content=response,
                    finish_reason="stop",
                    tokens_used=len(response.split()),
                )

        # Default mock response
        default = "def mock_function():\n    return True"
        return LLMResponse(
            content=default,
            finish_reason="stop",
            tokens_used=len(default.split()),
        )


def create_provider(
    provider_type: str,
    **kwargs: Any
) -> LLMProvider:
    """
    Factory function to create LLM providers.

    Args:
        provider_type: "claude", "openrouter", or "mock"
        **kwargs: Provider-specific arguments

    Returns:
        Configured LLMProvider instance
    """
    providers = {
        "claude": ClaudeProvider,
        "openrouter": OpenRouterProvider,
        "mock": MockProvider,
    }

    if provider_type not in providers:
        raise ValueError(
            f"Unknown provider: {provider_type}. "
            f"Supported: {', '.join(providers.keys())}"
        )

    return providers[provider_type](**kwargs)
