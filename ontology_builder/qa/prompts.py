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
        return f"\n\nLANGUAGE: You MUST respond entirely in {name}. The reasoning, the answer body, and the follow-up questions must all be in {name}. Do not mix languages."
    return "\n\nLANGUAGE: You MUST respond in the same language as the user's question. Detect the question language and use it for the reasoning, answer body, and follow-up questions. Do not default to English."


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


AGENT_QA_SYSTEM = """\
You answer questions about a domain using only the provided ontology information. You are helping a user explore and understand the knowledge base in depth.

The context is organized as:
1. **Ontological Context** — taxonomy information (superclasses, subclasses, definitions).
2. **Retrieved Facts** — specific facts from the knowledge graph discovered during multi-step exploration.

You must respond with valid JSON only, containing exactly two keys:
- "reasoning": An in-depth interpretation of the facts. Explain how they relate, what they imply, and how they connect to the question. Be thorough and analytical. Use plain language.
- "answer": A detailed, natural, and comprehensive answer. Structure it so the user learns everything relevant:
  * Start with a direct answer to the question.
  * Add relevant details: related concepts, how they connect, practical implications.
  * End with a follow-up section. Use the EXACT header "## You might also ask" (in English, always) followed by 2–4 natural follow-up questions the user could ask to explore further. Format as a Markdown heading then a bullet list, e.g.:
    ## You might also ask
    - What champions work well as midlaners?
    - How does warding help a midlaner?
    - What items should a midlaner build?

CRITICAL FORMATTING:
- The follow-up section header MUST be exactly "## You might also ask" (in English) regardless of the answer language. The UI parses this header.
- The answer body and follow-up questions must be in the requested answer language (or the question language if not specified).

Rules:
- Base BOTH reasoning and answer STRICTLY and ONLY on the provided facts. Do not infer, extrapolate, or add anything from your base knowledge.
- The answer must be fully supported by the facts. If the facts do not address part of the question, do NOT mention that information is missing, insufficient, or unavailable. Simply answer based on what the facts DO support.
- Use natural, conversational prose. Avoid robotic or list-heavy answers unless lists help clarity.
- Do not invent entities, relations, or numbers.
- NEVER mention node:, edge:, dp:, or bracketed IDs. Use entity names and natural language only."""

AGENT_QA_USER_TEMPLATE = """\
{ontological_context}

Retrieved facts from exploration:
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


def build_agent_qa_user_prompt(
    context: str,
    question: str,
    ontological_context: str = "",
    answer_language: str | None = None,
) -> str:
    """Build QA user prompt for agent mode: detailed answers with follow-up suggestions."""
    onto = ontological_context.strip() if ontological_context else "(no ontological context available)"
    answer_instruction = _answer_language_instruction(answer_language)
    return AGENT_QA_USER_TEMPLATE.format(
        ontological_context=onto,
        context=context.strip(),
        question=question.strip(),
        answer_language_instruction=answer_instruction,
    )
