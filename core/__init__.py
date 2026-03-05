"""Shared core package: config, constants."""

from core.config import Settings, get_settings
from core.constants import (
    CHARS_PER_TOKEN,
    CONFIDENCE_THRESHOLD,
    ENCODE_BATCH_SIZE,
    MAX_REASONING_ITERATIONS,
    MAX_RETRIEVAL_FACTS,
    SIMILARITY_THRESHOLD,
)

__all__ = [
    "Settings",
    "get_settings",
    "CHARS_PER_TOKEN",
    "CONFIDENCE_THRESHOLD",
    "ENCODE_BATCH_SIZE",
    "MAX_REASONING_ITERATIONS",
    "MAX_RETRIEVAL_FACTS",
    "SIMILARITY_THRESHOLD",
]
