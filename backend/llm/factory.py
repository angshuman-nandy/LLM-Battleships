# MIT License
# Copyright (c) 2026 Angshuman Nandy

from __future__ import annotations

from ..game.models import LLMConfig, Provider
from .base import LLMWrapper


class LLMWrapperFactory:
    """Instantiate the correct :class:`LLMWrapper` for a given :class:`LLMConfig`.

    Concrete wrapper modules are imported lazily inside each branch so that
    optional provider SDKs (``anthropic``, ``openai``) are only required at
    runtime when that provider is actually used — not at import time.
    """

    @staticmethod
    def create(config: LLMConfig) -> LLMWrapper:
        """Return a provider-specific :class:`LLMWrapper` for *config*.

        Args:
            config: Fully populated :class:`~backend.game.models.LLMConfig`
                including the provider type, model name, and API key.

        Returns:
            A concrete :class:`LLMWrapper` instance ready for use.

        Raises:
            ValueError: If *config.provider* is not a recognised :class:`Provider`.
        """
        if config.provider == Provider.anthropic:
            from .anthropic_wrapper import AnthropicWrapper
            return AnthropicWrapper(config)

        if config.provider == Provider.openai:
            from .openai_wrapper import OpenAIWrapper
            return OpenAIWrapper(config)

        raise ValueError(f"Unknown provider: {config.provider!r}")
