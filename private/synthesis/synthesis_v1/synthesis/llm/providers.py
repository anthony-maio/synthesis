"""
LLM provider abstractions for code generation.

This module defines the interface for LLM providers and implements concrete
providers for various services. The synthesizer uses these providers to generate
and refine code during the TDD process.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Any LLM service can be integrated by implementing this interface.
    The synthesizer is provider-agnostic and works with any implementation.
    """
    
    @abstractmethod
    async def generate_code(self,
                           prompt: str,
                           temperature: float = 0.7,
                           max_tokens: int = 2000) -> str:
        """
        Generate code based on a prompt.
        
        Args:
            prompt: The prompt describing what code to generate
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated code as a string
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        pass


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing and demonstrations.
    
    This provider doesn't actually call an LLM - instead it uses
    pattern matching and templates to generate reasonable code for
    common capability patterns. This is useful for:
    
    - Testing the synthesis framework without API costs
    - Demonstrations and examples
    - Development and debugging
    """
    
    def __init__(self):
        """Initialize the mock provider."""
        self.call_count = 0
    
    async def generate_code(self,
                           prompt: str,
                           temperature: float = 0.7,
                           max_tokens: int = 2000) -> str:
        """
        Generate mock code based on prompt patterns.
        
        Args:
            prompt: The prompt (analyzed for patterns)
            temperature: Ignored in mock
            max_tokens: Ignored in mock
            
        Returns:
            Generated code based on recognized patterns
        """
        self.call_count += 1
        
        # Try to detect what kind of capability is being requested
        prompt_lower = prompt.lower()
        
        # Math operations
        if any(word in prompt_lower for word in ['add', 'sum', 'plus', 'addition']):
            return self._generate_addition_code()
        
        if any(word in prompt_lower for word in ['multiply', 'product', 'times']):
            return self._generate_multiplication_code()
        
        # String operations
        if any(word in prompt_lower for word in ['uppercase', 'upper', 'capitalize']):
            return self._generate_uppercase_code()
        
        if any(word in prompt_lower for word in ['reverse', 'backwards']):
            return self._generate_reverse_code()
        
        # Default: simple echo
        return self._generate_echo_code()
    
    def _generate_addition_code(self) -> str:
        """Generate code for addition."""
        return '''def execute(a, b):
    """Add two numbers together."""
    return a + b
'''
    
    def _generate_multiplication_code(self) -> str:
        """Generate code for multiplication."""
        return '''def execute(a, b):
    """Multiply two numbers."""
    return a * b
'''
    
    def _generate_uppercase_code(self) -> str:
        """Generate code for uppercase conversion."""
        return '''def execute(text):
    """Convert text to uppercase."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    return text.upper()
'''
    
    def _generate_reverse_code(self) -> str:
        """Generate code for string reversal."""
        return '''def execute(text):
    """Reverse a string."""
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    return text[::-1]
'''
    
    def _generate_echo_code(self) -> str:
        """Generate default echo code."""
        return '''def execute(value):
    """Echo the input value."""
    return value
'''
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "MockLLMProvider"


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider for real code generation.
    
    This provider uses OpenAI's API (GPT-4, etc.) to generate code.
    Requires an API key to be configured.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model to use (e.g., "gpt-4", "gpt-3.5-turbo")
        """
        self.api_key = api_key
        self.model = model
        
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )
    
    async def generate_code(self,
                           prompt: str,
                           temperature: float = 0.7,
                           max_tokens: int = 2000) -> str:
        """
        Generate code using OpenAI API.
        
        Args:
            prompt: Code generation prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Generated code
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python programmer. Generate clean, correct, well-documented code."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            code = response.choices[0].message.content
            
            # Extract code from markdown if present
            code = self._extract_code_from_markdown(code)
            
            return code
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
    
    def _extract_code_from_markdown(self, text: str) -> str:
        """
        Extract code from markdown code blocks if present.
        
        Args:
            text: Text that might contain markdown code blocks
            
        Returns:
            Extracted code or original text
        """
        # Look for ```python code blocks
        import re
        pattern = r'```python\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Look for generic ``` code blocks
        pattern = r'```\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Return as-is if no code blocks found
        return text.strip()
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"OpenAI-{self.model}"


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider for code generation.
    
    Uses Claude models which can be excellent for code generation tasks.
    """
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Anthropic provider.
        
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
                "Anthropic package not installed. Install with: pip install anthropic"
            )
    
    async def generate_code(self,
                           prompt: str,
                           temperature: float = 0.7,
                           max_tokens: int = 2000) -> str:
        """
        Generate code using Anthropic API.
        
        Args:
            prompt: Code generation prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Generated code
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system="You are an expert Python programmer. Generate clean, correct, well-documented code. Return ONLY the code, no explanations.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            code = message.content[0].text
            
            # Extract code from markdown if present
            code = self._extract_code_from_markdown(code)
            
            return code
            
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}")
    
    def _extract_code_from_markdown(self, text: str) -> str:
        """Extract code from markdown blocks."""
        import re
        
        # Look for ```python code blocks
        pattern = r'```python\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Look for generic ``` code blocks
        pattern = r'```\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"Anthropic-{self.model}"
