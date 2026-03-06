"""Prompt templates for ontology-grounded QA (RAG) with fact-level attribution."""

# Language names for answer-language instruction (user's language, not ontology language)
_ANSWER_LANGUAGE_NAMES = {
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


def _answer_language_instruction(answer_language: str | None) -> str:
    """Return instruction so the model answers in the user's language (not the ontology language)."""
    if answer_language:
        name = _ANSWER_LANGUAGE_NAMES.get(answer_language.lower(), answer_language)
        return f"\n\nYou must respond in {name} only. Both the reasoning and answer must be in {name}."
    return "\n\nYou must respond in the same language as the user's question. Use that language for both the reasoning and the answer."


QA_SYSTEM = """\
You answer questions about a domain using only the provided ontology information.

The context is organized as:
1. **Ontological Context** — taxonomy information (superclasses, subclasses, definitions) that frames the domain.
2. **Retrieved Facts** — specific facts from the knowledge graph, each with a numeric reference in [brackets] for internal use only.

You must respond with valid JSON only, containing exactly two keys:
- "reasoning": An in-depth interpretation of the facts. Explain how the facts relate to each other, what they imply, how they connect to the question, and what conclusions can be drawn. Be thorough and analytical. Use plain language; translate graph relations (e.g., "Nexus is a type of structure" not "Nexus subClassOf Structure"). Do not mention node:, edge:, dp:, or bracketed IDs.
- "answer": A concise, user-friendly answer. Start with one short direct sentence. Use natural prose. Avoid robotic phrasing. Use Markdown headings and bullets only when they improve clarity. If helpful, add a brief ## Summary with 2-4 bullets.

Rules:
- Base BOTH reasoning and answer ONLY on the provided facts.
- If facts are insufficient, say exactly what is missing in both fields.
- Do not invent entities, relations, or numbers.
- NEVER mention node:, edge:, dp:, or bracketed source IDs. Use entity names and natural language only.
- You may infer obvious relationships from the facts (e.g., if A is a subclass of B and B is a subclass of C, explain the hierarchy in plain language)."""

QA_USER_TEMPLATE = """\
{ontological_context}

Retrieved facts:
{context}

Question: {question}
{answer_language_instruction}

Respond with JSON only: {{"reasoning": "...", "answer": "..."}}"""


def build_qa_user_prompt(
    context: str,
    question: str,
    ontological_context: str = "",
    answer_language: str | None = None,
) -> str:
    """Build QA user prompt with optional ontological context and answer language.

    answer_language: ISO 639-1 code (e.g. en, fr). If None, instructs the model to
    answer in the same language as the user's question (so the user always gets
    answers in their language regardless of ontology language).
    """
    onto = ontological_context.strip() if ontological_context else "(no ontological context available)"
    answer_instruction = _answer_language_instruction(answer_language)
    return QA_USER_TEMPLATE.format(
        ontological_context=onto,
        context=context.strip(),
        question=question.strip(),
        answer_language_instruction=answer_instruction,
    )
