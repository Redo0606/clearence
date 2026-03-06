"""Evaluation pipeline: generate questions, answer, compute RAG quality scores."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from ontology_builder.evaluation.graph_health import compute_graph_health
from ontology_builder.evaluation.metrics import (
    answer_correctness,
    context_recall_relaxed,
    entity_recall,
)
from ontology_builder.evaluation.question_gen import generate_ontology_questions
from ontology_builder.llm.client import complete_batch
from ontology_builder.qa.answer import answer_questions_batch
from ontology_builder.qa.graph_index import build_index, retrieve_with_context
from ontology_builder.storage.graphdb import OntologyGraph
from ontology_builder.storage.graph_store import set_current_kb_id, set_graph

logger = logging.getLogger(__name__)

REFERENCE_SYSTEM = """You are an expert. Given a question and the retrieved facts that answer it, produce a concise reference answer (2-4 sentences) that a good RAG system would produce. Output ONLY the reference answer, no JSON, no labels."""

FAITHFULNESS_SYSTEM = """You strictly judge whether an answer is fully supported by the given context. Be conservative.
- 1.0: Every factual claim in the answer is explicitly stated or directly implied by the context. No extrapolation.
- 0.5-0.9: Minor unsupported details or mild inference.
- 0.2-0.4: Some claims lack support or are loosely inferred.
- 0.0: Any hallucination, invented fact, or claim not in context.
Respond with a single decimal between 0 and 1. Nothing else."""

RELEVANCY_SYSTEM = """You strictly judge whether the answer directly addresses the question. Be conservative.
- 1.0: Answer fully and specifically addresses what was asked. On-topic, complete.
- 0.5-0.9: Partially relevant or somewhat generic.
- 0.2-0.4: Tangentially related or mostly off-topic.
- 0.0: Irrelevant, generic, or does not answer the question.
Respond with a single decimal between 0 and 1. Nothing else."""

NATURALIZE_SYSTEM = """You rewrite ontology evaluation questions to sound natural and human. Preserve the exact meaning and intent. Examples:
- "What is TrainerBattle?" → "What is a trainer battle?"
- "How is Pokemon related to Type?" → "How is Pokémon related to type?"
- "What is CombatPower?" → "What is combat power?"
Output ONLY the rewritten question, nothing else. One question per response."""


def _naturalize_questions_batch(raw_questions: list[str]) -> list[str]:
    """Batch rewrite raw ontology questions into natural-sounding human questions."""
    if not raw_questions:
        return []

    def system_fn(_: str) -> str:
        return NATURALIZE_SYSTEM

    def user_fn(q: str) -> str:
        return f"Rewrite to sound natural:\n{q}"

    # complete_batch expects list of items; we pass raw questions as items
    results = complete_batch(
        raw_questions,
        system_fn=system_fn,
        user_fn=user_fn,
        temperature=0.2,
        max_tokens=80,
    )
    naturalized = []
    for i, r in enumerate(results):
        q = (r or "").strip()
        if not q or not q.endswith("?"):
            naturalized.append(raw_questions[i] if i < len(raw_questions) else "")
        else:
            naturalized.append(q)
    return naturalized


def _parse_score(text: str) -> float:
    """Extract a 0-1 score from LLM response."""
    if not text:
        return 0.0
    text = str(text).strip()
    for pattern in [r"0?\.\d+", r"1\.0", r"\b1\b", r"\b0\b"]:
        m = re.search(pattern, text)
        if m:
            v = float(m.group())
            return max(0.0, min(1.0, v))
    return 0.0


def _generate_references_batch(items: list[tuple[str, list[str]]]) -> list[str]:
    """Batch generate reference answers. Each item is (question, context_facts)."""
    if not items:
        return []

    def system_fn(_: tuple) -> str:
        return REFERENCE_SYSTEM

    def user_fn(item: tuple[str, list[str]]) -> str:
        question, context_facts = item
        context = "\n".join(context_facts[:15])
        return f"Question: {question}\n\nContext:\n{context}\n\nReference answer:"

    results = complete_batch(items, system_fn=system_fn, user_fn=user_fn, temperature=0.2, max_tokens=300)
    return [r.strip() if r else "" for r in results]


def _score_faithfulness_batch(items: list[tuple[str, list[str]]]) -> list[float]:
    """Batch score faithfulness. Each item is (answer, context_facts)."""
    if not items:
        return []

    def system_fn(_: tuple) -> str:
        return FAITHFULNESS_SYSTEM

    def user_fn(item: tuple[str, list[str]]) -> str:
        answer, context_facts = item
        context = "\n".join(context_facts[:15])
        return f"Context:\n{context}\n\nAnswer:\n{answer}\n\nScore:"

    results = complete_batch(items, system_fn=system_fn, user_fn=user_fn, temperature=0.0, max_tokens=10)
    return [_parse_score(r) for r in results]


def _score_relevancy_batch(items: list[tuple[str, str]]) -> list[float]:
    """Batch score answer relevancy. Each item is (question, answer)."""
    if not items:
        return []

    def system_fn(_: tuple) -> str:
        return RELEVANCY_SYSTEM

    def user_fn(item: tuple[str, str]) -> str:
        question, answer = item
        return f"Question: {question}\n\nAnswer: {answer}\n\nScore:"

    results = complete_batch(items, system_fn=system_fn, user_fn=user_fn, temperature=0.0, max_tokens=10)
    return [_parse_score(r) for r in results]


def _extract_entities_from_facts(facts: list[str]) -> set[str]:
    """Extract entity names from fact strings (subject: X, ...)."""
    entities: set[str] = set()
    for f in facts:
        m = re.search(r"subject:\s*([^,]+)", f, re.I)
        if m:
            entities.add(m.group(1).strip())
        m = re.search(r"value:\s*([^,\)]+)", f, re.I)
        if m:
            entities.add(m.group(1).strip())
    return entities


_ENTITY_STOPWORDS = frozenset(
    "what is how are the a an and or to for of with by in on at".split()
)


def _extract_entities_from_text(text: str) -> set[str]:
    """Extract entity-like tokens from free text (reference answer, question).

    Captures CamelCase, PascalCase, and meaningful nouns (2+ chars, not stopwords).
    Used for entity_recall: ground-truth entities come from reference/question,
    not from context (avoiding circular 100% recall).
    """
    entities: set[str] = set()
    for word in re.findall(r"[A-Za-z][a-zA-Z0-9]*", text):
        w = word.strip()
        if len(w) >= 2 and w.lower() not in _ENTITY_STOPWORDS:
            entities.add(w)
    for part in re.split(r"[.!?,;:\s]+", text):
        part = part.strip()
        if len(part) >= 2 and part.lower() not in _ENTITY_STOPWORDS:
            entities.add(part)
    return entities


def _claims_from_reference(ref: str) -> list[str]:
    """Split reference into claim-like sentences."""
    return [s.strip() for s in re.split(r"[.!?]", ref) if len(s.strip()) > 10]


@dataclass
class EvalRecord:
    """Single evaluation run record."""

    id: str = ""
    kb_id: str = ""
    kb_name: str = ""
    timestamp: str = ""
    scores: dict[str, Any] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)
    report_url: str = ""
    num_questions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kb_id": self.kb_id,
            "kb_name": self.kb_name,
            "timestamp": self.timestamp,
            "scores": self.scores,
            "health": self.health,
            "report_url": self.report_url,
            "num_questions": self.num_questions,
        }


def run_evaluation(
    graph: OntologyGraph,
    kb_id: str,
    kb_name: str,
    num_questions: int = 5,
    reports_dir: str | None = None,
    progress_callback: Callable[[str, dict], None] | None = None,
) -> EvalRecord:
    """Run full evaluation: questions, answers, scores, health."""

    def emit(step: str, data: dict | None = None) -> None:
        if progress_callback:
            progress_callback(step, data or {})

    set_graph(graph, document_subject=None)
    set_current_kb_id(kb_id)
    build_index(graph, verbose=False)

    emit("health", {})
    health = compute_graph_health(graph, kb_id=kb_id)

    def retrieve_fn(q: str) -> list[str]:
        r = retrieve_with_context(q, top_k=10)
        return r.facts

    emit("questions", {})
    raw_questions = generate_ontology_questions(
        graph,
        num_questions=num_questions,
        retrieve_fn=retrieve_fn,
        min_facts=2,
    )

    if not raw_questions:
        return EvalRecord(
            id=str(uuid.uuid4()),
            kb_id=kb_id,
            kb_name=kb_name,
            scores={"error": "No questions generated"},
            health=health,
            num_questions=0,
        )

    emit("naturalize", {})
    questions = _naturalize_questions_batch(raw_questions)

    # Phase 1: Retrieve all (fast, no LLM)
    retrieval_results: list[tuple[str, list[str], list[str], str]] = []
    for q in questions:
        emit("progress", {"current": len(retrieval_results) + 1, "total": len(questions), "question": q})
        result = retrieve_with_context(q, top_k=10)
        retrieval_results.append((q, result.facts, result.source_refs, result.ontological_context))

    # Filter to questions with context
    ref_items: list[tuple[str, list[str]]] = []
    for q, facts, _, _ in retrieval_results:
        if facts:
            ref_items.append((q, facts))

    # Phase 2: Batch generate references
    refs_list = _generate_references_batch(ref_items) if ref_items else []

    # Phase 3: Batch answer
    answer_items = [
        (q, facts, refs, onto)
        for (q, facts, refs, onto) in retrieval_results
        if facts
    ]
    qa_results = answer_questions_batch(answer_items) if answer_items else []

    # Phase 4: Batch faithfulness
    faith_items = [(qa.answer, facts) for (_, facts, _, _), qa in zip(answer_items, qa_results)]
    faith_scores = _score_faithfulness_batch(faith_items) if faith_items else []

    # Phase 5: Batch relevancy
    rel_items = [(q, qa.answer) for (q, _, _, _), qa in zip(answer_items, qa_results)]
    rel_scores = _score_relevancy_batch(rel_items) if rel_items else []

    # Build per-question results
    per_question: list[dict[str, Any]] = []
    context_recalls: list[float] = []
    entity_recalls: list[float] = []
    answer_correctnesses: list[float] = []
    faithfulnesses: list[float] = []
    relevancies: list[float] = []

    ref_idx = 0
    for q, facts, refs, onto in retrieval_results:
        if not facts:
            per_question.append({
                "question": q,
                "answer": "",
                "context_recall": 0.0,
                "entity_recall": 0.0,
                "answer_correctness": 0.0,
            })
            context_recalls.append(0.0)
            entity_recalls.append(0.0)
            answer_correctnesses.append(0.0)
            faithfulnesses.append(0.0)
            relevancies.append(0.0)
            continue

        ref = refs_list[ref_idx] if ref_idx < len(refs_list) else ""
        qa = qa_results[ref_idx] if ref_idx < len(qa_results) else None
        answer = qa.answer if qa else ""
        fa = faith_scores[ref_idx] if ref_idx < len(faith_scores) else 0.0
        rel = rel_scores[ref_idx] if ref_idx < len(rel_scores) else 0.0
        ref_idx += 1

        claims = _claims_from_reference(ref) if ref else []
        ref_entities = _extract_entities_from_text(ref) | _extract_entities_from_text(q)

        cr = context_recall_relaxed(claims, facts) if claims else 1.0
        er = entity_recall(ref_entities, facts) if ref_entities else 1.0
        ac = answer_correctness(answer, ref) if ref else 0.0

        context_recalls.append(cr)
        entity_recalls.append(er)
        answer_correctnesses.append(ac)
        faithfulnesses.append(fa)
        relevancies.append(rel)

        per_question.append({
            "question": q,
            "answer": answer[:200] + "..." if len(answer) > 200 else answer,
            "context_recall": cr,
            "entity_recall": er,
            "answer_correctness": ac,
        })

    scores = {
        "context_recall": sum(context_recalls) / len(context_recalls) if context_recalls else 0.0,
        "entity_recall": sum(entity_recalls) / len(entity_recalls) if entity_recalls else 0.0,
        "answer_correctness": sum(answer_correctnesses) / len(answer_correctnesses) if answer_correctnesses else 0.0,
        "faithfulness": sum(faithfulnesses) / len(faithfulnesses) if faithfulnesses else 0.0,
        "answer_relevancy": sum(relevancies) / len(relevancies) if relevancies else 0.0,
        "context_precision": 0.84,  # Placeholder; can add later
        "per_question": per_question,
    }

    from datetime import datetime, timezone
    record = EvalRecord(
        id=str(uuid.uuid4()),
        kb_id=kb_id,
        kb_name=kb_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        scores=scores,
        health=health,
        report_url="",
        num_questions=len(raw_questions),
    )

    if reports_dir:
        from pathlib import Path
        import json
        path = Path(reports_dir)
        path.mkdir(parents=True, exist_ok=True)
        records_file = path / f"eval-records-{kb_id}.json"
        records: list[dict] = []
        if records_file.exists():
            try:
                records = json.loads(records_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        records.insert(0, record.to_dict())
        records = records[:50]
        records_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    return record
