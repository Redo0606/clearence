"""LLM prompts for sequential ontology extraction (Bakker approach B) and inference.

Three-stage extraction:
  1. Extract classes/concepts
  2. Given classes, extract instances/individuals
  3. Given classes + instances, extract relations, data properties, and axioms

Each stage returns structured JSON matching the formal schema O = {C, R, I, P}.
"""

# ---------------------------------------------------------------------------
# Stage 1: Class / concept extraction
# ---------------------------------------------------------------------------

EXTRACT_CLASSES_SYSTEM = (
    "You are a formal ontology engineer. "
    "Extract only the conceptual classes (universals / categories) from the text. "
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
      "description": "<one-sentence definition>"
    }}
  ]
}}

Rules:
- Use CamelCase for class names.
- Set "parent" only when the text explicitly states an is-a / subclass relationship.
- Every class must have a non-empty description grounded in the text.

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
      "description": "<brief description>"
    }}
  ]
}}

Rules:
- Only create instances that are explicitly mentioned in the text.
- class_name MUST be one of the known classes listed above.

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
      "confidence": 0.9
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
- confidence must be between 0 and 1 based on how explicitly the text supports the relation.
- Only include axioms if the text provides evidence for them.

Text:
{chunk}
"""

# ---------------------------------------------------------------------------
# Legacy single-shot prompt (kept for backward compat / simple mode)
# ---------------------------------------------------------------------------

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

Return valid JSON only (no markdown, no code fences). Use one top-level key:
- relations: array of objects, each with source, relation, target, and confidence (0 to 1)

Ontology graph:
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
