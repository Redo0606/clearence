"""LLM prompts for sequential ontology extraction (Bakker approach B) and inference.

Three-stage extraction:
  1. Extract classes/concepts
  2. Given classes, extract instances/individuals
  3. Given classes + instances, extract relations, data properties, and axioms

Each stage returns structured JSON matching the formal schema O = {C, R, I, P}.
"""

# Common language names for ontology output (so the model uses one language for all node/edge text)
_LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
}


def ontology_language_instruction(lang: str) -> str:
    """Return instruction so the model outputs all ontology elements (names, descriptions, labels) in the given language only."""
    if not lang or lang.lower() == "en":
        return ""
    name = _LANGUAGE_NAMES.get(lang.lower(), lang)
    return (
        f"\n\nImportant: Output ALL class names, instance names, descriptions, relation labels, synonyms, and any other text in the ontology strictly in {name} only. "
        "Do not mix languages; every name and description must be in this language."
    )


def inference_language_instruction(lang: str) -> str:
    """Return instruction for relation inference so inferred relation labels and entity names stay in the ontology language."""
    if not lang or lang.lower() == "en":
        return ""
    name = _LANGUAGE_NAMES.get(lang.lower(), lang)
    return (
        f"\n\nOutput all relation labels and any new entity names strictly in {name} only (same language as the existing ontology)."
    )


# ---------------------------------------------------------------------------
# Stage 1: Class / concept extraction
# ---------------------------------------------------------------------------

EXTRACT_CLASSES_SYSTEM = (
    "You are a formal ontology engineer. "
    "Extract only the conceptual classes (universals / categories) from the text. "
    "Extract only classes that represent general categories or types, not specific named individuals or one-off instances. "
    "Prefer broader classes over overly narrow subclasses unless the document explicitly distinguishes them. "
    "Do not invent classes that are not evidenced in the provided text. "
    "Output ONLY valid JSON — no markdown, no code fences, no commentary."
)

EXTRACT_CLASSES_USER = """\
Analyze the following text and extract all ontology **classes** (concepts, categories, types — NOT individual instances).

Return a JSON object:
{{
  "classes": [
    {{
      "name": "<ClassName>",
      "parent": "<ParentClassName or null>",
      "description": "<one-sentence definition>",
      "synonyms": ["<alternative name 1>", "<alternative name 2>"],
      "salience": 0.0-1.0,
      "domain_tags": ["<tag1>", "<tag2>"]
    }}
  ]
}}

- salience: A float from 0.0 to 1.0 indicating how central this class is to the domain. Core domain concepts = 0.8+. Generic concepts = 0.2.
- domain_tags: List of short domain area labels this class belongs to (e.g. ["gameplay", "character"]).

Rules:
- Use CamelCase for class names.
- Include "synonyms" only when the text uses alternative terms for the same concept (e.g. "Vehicle" -> ["Car", "Automobile"]).
- Set "parent" only when the text explicitly states an is-a / subclass relationship.
- Every class must have a non-empty description grounded in the text.
- Extract no more than 20 classes per chunk.

Do NOT extract:
- Hallucinated classes (e.g. "QuantumEntanglementModule" when the text only discusses vehicles).
- Specific instances as classes (e.g. "JohnSmith" or "ProjectAlpha" as a class; use them as instances of a class like "Person" or "Project").
{ontology_language_instruction}

Text:
{chunk}
"""

# ---------------------------------------------------------------------------
# Stage 2: Instance / individual extraction
# ---------------------------------------------------------------------------

EXTRACT_INSTANCES_SYSTEM = (
    "You are a formal ontology engineer. "
    "Given a list of known classes and a text, extract concrete instances (individuals / particulars). "
    "Output ONLY valid JSON — no markdown, no code fences, no commentary."
)

EXTRACT_INSTANCES_USER = """\
Known classes: {classes_json}

Analyze the text and extract **instances** (named individuals, specific entities) that belong to the classes above.

Return a JSON object:
{{
  "instances": [
    {{
      "name": "<instance name>",
      "class_name": "<ClassName it belongs to>",
      "description": "<brief description>",
      "attributes": {{"<key>": "<value>", ...}}
    }}
  ]
}}

- attributes: A dict of known factual key-value attributes for this instance. Examples: {{"role": "Fighter", "region": "Demacia", "difficulty": "Low"}}. Only include attributes explicitly stated in the text.

Rules:
- Only create instances that are explicitly mentioned in the text.
- class_name MUST be one of the known classes listed above.
{ontology_language_instruction}

Text:
{chunk}
"""

# ---------------------------------------------------------------------------
# Stage 3: Relations, data properties, axioms
# ---------------------------------------------------------------------------

EXTRACT_RELATIONS_SYSTEM = (
    "You are a formal ontology engineer. "
    "Given classes, instances, and text, extract object properties (relations), data properties, and axioms. "
    "Output ONLY valid JSON — no markdown, no code fences, no commentary."
)

EXTRACT_RELATIONS_USER = """\
Known classes: {classes_json}
Known instances: {instances_json}

Analyze the text and extract:
1. **object_properties** — binary relations between any two entities (classes or instances).
2. **data_properties** — literal attribute-value pairs attached to an entity.
3. **axioms** — formal constraints (disjointness, symmetry, transitivity, subclass, etc.).

Return a JSON object:
{{
  "object_properties": [
    {{
      "source": "<entity name>",
      "relation": "<relation label>",
      "target": "<entity name>",
      "domain": "<class or null>",
      "range": "<class or null>",
      "symmetric": false,
      "transitive": false,
      "confidence": 0.9,
      "evidence": "<quote from text>",
      "relation_type": "<taxonomic|compositional|functional|causal|associative>",
      "bidirectional": false
    }}
  ],
  "data_properties": [
    {{
      "entity": "<entity name>",
      "attribute": "<attribute name>",
      "value": "<literal value>",
      "datatype": "string"
    }}
  ],
  "axioms": [
    {{
      "axiom_type": "<disjointness|symmetry|transitivity|asymmetry|inverse|functional|subclass>",
      "entities": ["<entity1>", "<entity2>"],
      "description": "<why this axiom holds>"
    }}
  ]
}}

Rules:
- Prefer these relation names: subClassOf, hasPart, hasAbility, causes, relatedTo. Map similar concepts to these canonical names.
- confidence must be between 0 and 1 based on how explicitly the text supports the relation.
- evidence: Quote the exact sentence(s) from the text that support this relation.
- relation_type: Classify as one of: taxonomic, compositional, functional, causal, associative.
- bidirectional: True only if the relation clearly holds in both directions.
- Only include axioms if the text provides evidence for them.
{ontology_language_instruction}

Text:
{chunk}
"""

# ---------------------------------------------------------------------------
# Legacy single-shot prompt (kept for backward compat / simple mode)
# ---------------------------------------------------------------------------

def build_legacy_extraction_prompt(ontology_language: str = "en") -> str:
    """Build legacy single-shot extraction prompt with optional language constraint."""
    lang_instruction = ontology_language_instruction(ontology_language)
    return f"""\
You are an ontology engineer. Extract ontology components from the text.

Return valid JSON only (no markdown, no code fences). Use exactly two top-level keys:
- entities: array of objects, each with name, type, and description
- relations: array of objects, each with source, relation, target, and confidence (0 to 1)

Extract all important concepts as entities and relationships between them as relations.
{lang_instruction}

Text:
"""


ONTOLOGY_EXTRACTION_PROMPT = """\
You are an ontology engineer. Extract ontology components from the text.

Return valid JSON only (no markdown, no code fences). Use exactly two top-level keys:
- entities: array of objects, each with name, type, and description
- relations: array of objects, each with source, relation, target, and confidence (0 to 1)

Extract all important concepts as entities and relationships between them as relations.

Text:
"""

# ---------------------------------------------------------------------------
# Relation inference prompt
# ---------------------------------------------------------------------------

INFERENCE_PROMPT = """\
Given an ontology graph, infer subclass relations, causal relations, dependencies, rules, and missing connections.
Prioritize inferring relations between entities that appear in different clusters or sections of the graph, to connect otherwise disconnected parts.

Return valid JSON only (no markdown, no code fences). Use one top-level key:
- relations: array of objects, each with source, relation, target, and confidence (0 to 1)

Ontology graph:
"""

# Used by cross-component relation inference (entity pairs from disconnected clusters)
CROSS_COMPONENT_INFERENCE_PROMPT = """\
Given an ontology graph and a list of entity pairs from different disconnected clusters, infer plausible relations that could connect them (e.g. part_of, depends_on, related_to, type, subClassOf).

Return valid JSON only (no markdown, no code fences). Use one top-level key:
- relations: array of objects, each with source, relation, target, and confidence (0 to 1). Only include relations where both source and target are from the entity pairs or the graph.

Ontology graph (summary):
{graph_summary}

Entity pairs to connect (source, target from different clusters):
{pairs_text}
"""

# ---------------------------------------------------------------------------
# Taxonomy organization prompt (OntoGen-style)
# ---------------------------------------------------------------------------

TAXONOMY_SYSTEM = (
    "You are a formal ontology engineer specializing in taxonomy construction. "
    "Output ONLY valid JSON — no markdown, no code fences, no commentary."
)

TAXONOMY_USER = """\
Given these ontology classes extracted from a document, organize them into a \
taxonomic hierarchy using is-a (subclass) relationships.

Classes: {classes_json}

Return a JSON object:
{{
  "taxonomy": [
    {{
      "name": "<ClassName>",
      "parent": "<ParentClassName or null>",
      "description": "<one-sentence definition>"
    }}
  ]
}}

Rules:
- Every input class MUST appear in the output.
- Set "parent" to null for top-level (root) classes.
- Do NOT invent new classes that are not in the input list.
- A class cannot be its own parent.
"""
