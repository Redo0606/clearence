"""Prompt templates for ontology-grounded QA (RAG) with fact-level attribution."""

QA_SYSTEM = """\
You answer questions about a domain using only the provided ontology information.

The context is organized as:
1. **Ontological Context** — taxonomy information (superclasses, subclasses, definitions) \
that frames the domain.
2. **Retrieved Facts** — specific facts from the knowledge graph, each with a source reference \
in [brackets].

Rules:
- Base your answer ONLY on the provided facts.
- When stating a claim, cite the source reference(s) that support it, e.g. [edge:X-rel-Y].
- If the facts do not contain enough information, say so explicitly.
- Be concise and structured."""

QA_USER_TEMPLATE = """\
{ontological_context}

Retrieved facts:
{context}

Question: {question}

Answer (cite sources):"""


def build_qa_user_prompt(
    context: str,
    question: str,
    ontological_context: str = "",
) -> str:
    """Build QA user prompt with optional ontological context."""
    onto = ontological_context.strip() if ontological_context else "(no ontological context available)"
    return QA_USER_TEMPLATE.format(
        ontological_context=onto,
        context=context.strip(),
        question=question.strip(),
    )
