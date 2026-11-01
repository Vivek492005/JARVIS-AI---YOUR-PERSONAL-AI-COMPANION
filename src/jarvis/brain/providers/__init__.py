"""LLM/STT/TTS provider abstraction (Master Plan Task 2.5)."""

from jarvis.brain.providers.base import (Completion, LLMProvider, STTProvider,
                                          ToolCall, TTSProvider)
from jarvis.brain.providers.chain import ChainResult, ProviderChain
from jarvis.brain.providers.local import LocalHeuristicProvider
from jarvis.brain.providers.openai_compat import (DeepSeek,
                                                  HuggingFaceRouter, Ollama,
                                                  OpenAICompatibleProvider)

__all__ = [
    "Completion", "ToolCall", "LLMProvider", "STTProvider", "TTSProvider",
    "ChainResult", "ProviderChain", "LocalHeuristicProvider",
    "OpenAICompatibleProvider", "HuggingFaceRouter", "DeepSeek", "Ollama",
]
