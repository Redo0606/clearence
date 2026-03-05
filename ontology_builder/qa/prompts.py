"""Prompt templates for ontology QA (RAG)."""

QA_SYSTEM = """You answer questions about a domain using only the provided ontology information.
The context is provided as a list of facts. Each fact has subject, attribute, and value.
Answer concisely and base your answer only on the given facts.
When possible, cite specific subjects and values from the context."""

QA_USER_TEMPLATE = """Ontology facts (subject, attribute, value):
{context}

Question: {question}

Answer:"""


def build_qa_user_prompt(context: str, question: str) -> str:
    """Build QA user prompt from context facts and question."""
    return QA_USER_TEMPLATE.format(context=context.strip(), question=question.strip())
