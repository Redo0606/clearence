"""LLM prompts for ontology extraction and relation inference."""

ONTOLOGY_EXTRACTION_PROMPT = """You are an ontology engineer.

Extract ontology components from the text.

Return valid JSON only (no markdown, no code fences) with this structure:

{
  "entities": [
    {"name": "EntityName", "type": "ConceptType", "description": "Brief description"}
  ],
  "relations": [
    {"source": "EntityA", "relation": "relation_type", "target": "EntityB", "confidence": 0.9}
  ]
}

Extract all important concepts as entities (name, type, description) and relationships between them (source, relation, target, confidence between 0 and 1).

Text:
"""

INFERENCE_PROMPT = """Given an ontology graph, infer:

- subclass relations
- causal relations
- dependencies
- rules
- missing connections

Return new relations as valid JSON only (no markdown) in this form:

{
  "relations": [
    {"source": "EntityA", "relation": "relation_type", "target": "EntityB", "confidence": 0.8}
  ]
}

Ontology graph:
"""
