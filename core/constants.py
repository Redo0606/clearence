"""Shared constants for ontology extraction, reasoning, and retrieval.

Centralizes magic numbers with documented rationale for maintainability.
"""

# Conservative estimate for English text (1 token ≈ 4 chars). Used for token budget guards.
CHARS_PER_TOKEN = 4

# Cosine similarity >= threshold maps to same canonical entity (embedding deduplication).
SIMILARITY_THRESHOLD = 0.9

# OWL 2 RL fixpoint iteration cap; prevents infinite loops.
MAX_REASONING_ITERATIONS = 20

# Min confidence for LLM-inferred relations to be accepted.
CONFIDENCE_THRESHOLD = 0.5

# Embedding batch size for SentenceTransformer (balance speed vs memory).
ENCODE_BATCH_SIZE = 64

# Max facts returned in retrieval; caps context size for LLM.
MAX_RETRIEVAL_FACTS = 20
