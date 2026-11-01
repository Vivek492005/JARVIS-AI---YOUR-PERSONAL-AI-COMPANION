"""Shared exception hierarchy (Phase 2 core)."""


class JarvisError(Exception):
    """Base for all JARVIS runtime errors."""


class ProviderError(JarvisError):
    """An LLM/STT/TTS provider failed (network, auth, quota, timeout)."""


class QuotaExhaustedError(ProviderError):
    """Provider answered 429 / quota-exhausted — skip straight to the next."""


class ToolError(JarvisError):
    """A tool executor failed after passing the policy gate."""


class ConfirmationTimeout(JarvisError):
    """A pending confirmation was not answered in time (fail-closed)."""


class LaneCancelled(JarvisError):
    """A queued/running lane item was cancelled (e.g. by Interrupt)."""
