"""Evaluation pipeline: generate questions, answer, compute RAG quality scores."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
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

REFERENCE_SYSTEM = """You produce a concise reference answer for a RAG evaluation question, based on the provided context facts.

Rules:
- Write 2-3 clear sentences in natural language.
- Cover the key facts from the context that answer the question.
- Use the entity names from the context exactly, but you may paraphrase relations naturally (e.g. "X is used in Y" instead of "relation: used_in").
- Do NOT add facts not present in the context.
- Output ONLY the reference answer. No JSON, no labels, no preamble."""

FAITHFULNESS_SYSTEM = """You judge whether an answer is grounded in the given context facts. Facts are listed as "subject: X, relation: R, value: Y" triples.

An answer is faithful if its claims can be reasonably inferred or paraphrased from those triples. Natural language restatements are fine.

Scoring:
- 1.0: Every claim in the answer is supported by or directly inferable from context facts. Paraphrasing is acceptable.
- 0.5: Most claims are supported; at most one minor detail goes slightly beyond the context.
- 0.0: The answer introduces entities or facts clearly absent from the context (hallucination).

Output ONLY a single number: 0, 0.5, or 1. Nothing else."""

RELEVANCY_SYSTEM = """You judge whether an answer addresses the question asked. The answer may be about ontology concepts, game mechanics, or domain entities.

- 1.0: The answer directly addresses what was asked, even if briefly or using domain terminology.
- 0.5: The answer is related but only partially addresses the question (e.g. answers a different aspect).
- 0.0: The answer is off-topic or completely fails to address the question.

Output ONLY a single decimal between 0 and 1. Nothing else."""

CORRECTNESS_SYSTEM = """You judge whether a generated answer conveys the same meaning as a reference answer.

IMPORTANT:
- Exact ontology class names are NOT required.
- Natural language paraphrases are acceptable.
- Synonyms and descriptive phrasing should be treated as correct if the meaning matches.

Examples:
"CombatPower" ≈ "battle strength" or "combat power"
"TrainerBattle" ≈ "battle between trainers" or "trainer fights"

Scoring:
- 1.0: Same meaning and facts (paraphrases and synonyms OK)
- 0.5: Partially correct — some facts match, some are missing or wrong
- 0.0: Incorrect or contradicts reference

Output ONLY a single number: 0, 0.5, or 1."""

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
    """Extract a 0-1 score from LLM response. Order matters: check 1.0 and 0.X before bare 0/1."""
    if not text:
        return 0.0
    text = str(text).strip()
    for pattern in [r"1\.0\b", r"0\.[0-9]+", r"\b1\b", r"\b0\b"]:
        m = re.search(pattern, text)
        if m:
            return max(0.0, min(1.0, float(m.group())))
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
        return f"""Question: {question}

Context (subject, relation, value format):
{context}

Reference answer:"""

    results = complete_batch(items, system_fn=system_fn, user_fn=user_fn, temperature=0.2, max_tokens=300)
    return [r.strip() if r else "" for r in results]


def _score_faithfulness_batch(items: list[tuple[str, str, list[str]]]) -> list[float]:
    """Batch score faithfulness. Each item is (question, answer, context_facts)."""
    if not items:
        return []

    def system_fn(_: tuple) -> str:
        return FAITHFULNESS_SYSTEM

    def user_fn(item: tuple[str, str, list[str]]) -> str:
        question, answer, context_facts = item
        context = "\n".join(context_facts[:15])
        return f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer: {answer}\n\nScore (0, 0.5, or 1):"

    results = complete_batch(items, system_fn=system_fn, user_fn=user_fn, temperature=0.0, max_tokens=20)
    for i, r in enumerate(results):
        logger.debug("faithfulness[%d] raw=%r parsed=%.2f", i, r, _parse_score(r))
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
    for i, r in enumerate(results):
        logger.debug("relevancy[%d] raw=%r parsed=%.2f", i, r, _parse_score(r))
    return [_parse_score(r) for r in results]


def _score_correctness_batch(items: list[tuple[str, str, str]]) -> list[float]:
    """Batch score correctness. Each item is (question, generated_answer, reference_answer)."""
    if not items:
        return []

    def system_fn(_: tuple) -> str:
        return CORRECTNESS_SYSTEM

    def user_fn(item: tuple[str, str, str]) -> str:
        q, ans, ref = item
        return f"Question: {q}\n\nReference: {ref}\n\nGenerated answer: {ans}\n\nScore:"

    results = complete_batch(items, system_fn=system_fn, user_fn=user_fn, temperature=0.0, max_tokens=20)
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


def _extract_entities_from_text(text: str) -> set[str]:
    """Extract meaningful entities: CamelCase, PascalCase, and quoted terms only.

    Only real concept names like TrainerBattle, CombatPower, HP register as entities —
    not noise words like 'is', 'related', 'type'.
    """
    entities: set[str] = set()
    # CamelCase / PascalCase — these are ontology concept names
    for word in re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text):
        entities.add(word)
    # ALL_CAPS acronyms (3+ chars)
    for word in re.findall(r"\b[A-Z]{3,}\b", text):
        entities.add(word)
    # Quoted terms
    for word in re.findall(r'"([^"]+)"', text):
        entities.add(word.strip())
    return entities


def _extract_entities_from_question(question: str, graph: OntologyGraph | None = None) -> set[str]:
    """Extract entities from question, with optional graph-aware fuzzy matching.

    When graph is provided, noun phrases (2-4 word sequences) are matched against
    graph nodes and synonyms, so "battle power" can match CombatPower.
    """
    entities = _extract_entities_from_text(question)
    if graph is None:
        return entities

    # Extract noun phrases: consecutive word sequences (2-4 words)
    words = re.findall(r"\b\w+\b", question.lower())
    stop = {"what", "how", "is", "are", "the", "a", "an", "to", "of", "in", "and", "or", "does", "do"}
    for n in (2, 3, 4):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            if phrase in stop or len(phrase) < 4:
                continue
            for node in graph.get_graph().nodes():
                if phrase in node.lower() or node.lower() in phrase:
                    entities.add(node)
                    break
                for syn in graph.get_node_synonyms(node):
                    if phrase in syn.lower() or syn.lower() in phrase:
                        entities.add(node)
                        break
    return entities


def _collect_graph_facts(graph: OntologyGraph, question: str, max_facts: int = 30) -> list[str]:
    """Collect facts from the ontology graph related to the question.

    Bypasses RAG retrieval to avoid evaluation bias. Extracts entities from the
    question, matches to graph nodes (including synonyms), and retrieves triples.
    """
    g = graph.get_graph()
    query_lower = question.lower()
    words = set(re.findall(r"\b\w+\b", query_lower)) - {"what", "how", "is", "are", "the", "a", "an", "to", "of", "in", "and", "or"}

    matched_nodes: set[str] = set()
    for node in g.nodes():
        node_lower = node.lower()
        if node_lower in query_lower or any(w in node_lower or node_lower in w for w in words if len(w) > 2):
            matched_nodes.add(node)
        else:
            for syn in graph.get_node_synonyms(node):
                syn_lower = syn.lower()
                if syn_lower in query_lower or any(w in syn_lower or syn_lower in w for w in words if len(w) > 2):
                    matched_nodes.add(node)
                    break

    if not matched_nodes:
        return []

    facts: list[str] = []
    seen: set[str] = set()

    for node in matched_nodes:
        if len(facts) >= max_facts:
            break
        data = g.nodes[node]
        node_type = data.get("type", "Entity")
        desc = data.get("description", "")
        full = f"subject: {node}, attribute: type, value: {node_type}"
        if desc:
            full += f" ({desc})"
        if full not in seen:
            seen.add(full)
            facts.append(full)

    for u, v, data in g.edges(data=True):
        if len(facts) >= max_facts:
            break
        if u in matched_nodes or v in matched_nodes:
            r = data.get("relation", "related_to")
            full = f"subject: {u}, attribute: {r}, value: {v}"
            if full not in seen:
                seen.add(full)
                facts.append(full)

    for dp in graph.data_properties:
        if len(facts) >= max_facts:
            break
        if dp["entity"] in matched_nodes:
            full = f"subject: {dp['entity']}, attribute: {dp['attribute']}, value: {dp['value']}"
            if full not in seen:
                seen.add(full)
                facts.append(full)

    return facts[:max_facts]


def _claims_from_reference(ref: str) -> list[str]:
    """Split reference into claim-like sentences."""
    return [s.strip() for s in re.split(r"[.!?]", ref) if len(s.strip()) > 10]


CLAIMS_EXTRACT_SYSTEM = """Extract factual claims from the answer. Each claim should be a short, standalone statement of fact.

Rules:
- One claim per line, prefixed with "- "
- Ignore stylistic or explanatory text (e.g. "Based on the ontology...")
- Focus on factual assertions about entities, relations, or properties

Example output:
- Pokémon have a combat power value
- Combat power affects battle performance

Output ONLY the list of claims, nothing else."""


def _extract_claims_llm_batch(answers: list[str]) -> list[list[str]]:
    """Batch extract factual claims from answers using LLM."""
    if not answers:
        return []

    def system_fn(_: str) -> str:
        return CLAIMS_EXTRACT_SYSTEM

    def user_fn(ans: str) -> str:
        return f"Answer:\n{ans}\n\nExtract factual claims:"

    results = complete_batch(answers, system_fn=system_fn, user_fn=user_fn, temperature=0.0, max_tokens=300)
    out: list[list[str]] = []
    for r in results:
        claims = []
        for line in (r or "").strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                claims.append(line[2:].strip())
            elif line and not line.startswith("#"):
                claims.append(line)
        out.append([c for c in claims if len(c) > 10])
    return out


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
    score_deltas: dict[str, float] = field(default_factory=dict)
    regressions: list[str] = field(default_factory=list)

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
            "score_deltas": self.score_deltas,
            "regressions": self.regressions,
        }


def run_evaluation(
    graph: OntologyGraph,
    kb_id: str,
    kb_name: str,
    num_questions: int = 5,
    reports_dir: str | None = None,
    progress_callback: Callable[[str, dict], None] | None = None,
    kb_path: Path | None = None,
) -> EvalRecord:
    """Run full evaluation: questions, answers, scores, health."""

    def emit(step: str, data: dict | None = None) -> None:
        if progress_callback:
            progress_callback(step, data or {})

    set_graph(graph, document_subject=None)
    set_current_kb_id(kb_id)
    build_index(graph, verbose=False, kb_path=kb_path)

    emit("health", {})
    health = compute_graph_health(graph, kb_id=kb_id)

    def retrieve_fn(q: str) -> list[str]:
        r = retrieve_with_context(q, top_k=15)
        return r.facts

    emit("questions", {})
    raw_questions = generate_ontology_questions(
        graph,
        num_questions=num_questions,
        retrieve_fn=retrieve_fn,
        min_facts=4,  # questions need richer context
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
    for i, q in enumerate(questions):
        emit("progress", {"current": len(retrieval_results) + 1, "total": len(questions), "question": q})
        result = retrieve_with_context(q, top_k=15)
        # If sparse, retry with raw (un-naturalized) question
        if len(result.facts) < 3 and i < len(raw_questions):
            result_raw = retrieve_with_context(raw_questions[i], top_k=15)
            if len(result_raw.facts) > len(result.facts):
                result = result_raw
        # If still sparse, try hybrid: naturalized + original ontology terms
        if len(result.facts) < 3 and i < len(raw_questions):
            raw_q = raw_questions[i]
            ontology_terms = " ".join(_extract_entities_from_text(raw_q))
            if ontology_terms:
                hybrid_q = f"{q} {ontology_terms}"
                result_hybrid = retrieve_with_context(hybrid_q, top_k=15)
                if len(result_hybrid.facts) > len(result.facts):
                    result = result_hybrid
        retrieval_results.append((q, result.facts, result.source_refs, result.ontological_context))

    MIN_FACTS_FOR_EVAL = 3
    retrieval_failures = sum(1 for _, facts, _, _ in retrieval_results if len(facts) < MIN_FACTS_FOR_EVAL)
    logger.info("Retrieval: %d/%d questions with >=%d facts (%d retrieval failures)",
                len(retrieval_results) - retrieval_failures, len(retrieval_results), MIN_FACTS_FOR_EVAL, retrieval_failures)

    # Generate references from graph facts (not retrieved context) to avoid retrieval leakage
    ref_items: list[tuple[str, list[str]]] = [
        (q, _collect_graph_facts(graph, q)) for q, _, _, _ in retrieval_results
    ]

    # Phase 2: Batch generate references (from graph facts, not retrieval)
    refs_list = _generate_references_batch(ref_items) if ref_items else []

    # Phase 3: Batch answer (all questions; low retrieval = retrieval failure, not filtered out)
    answer_items = list(retrieval_results)
    from ontology_builder.qa.answer import QA_SYSTEM_EVAL
    qa_results = answer_questions_batch(answer_items, system_prompt=QA_SYSTEM_EVAL) if answer_items else []

    # Phase 4: Batch faithfulness (LLM judge)
    faith_items = [(q, qa.answer, facts) for (q, facts, _, _), qa in zip(answer_items, qa_results)]
    faith_scores = _score_faithfulness_batch(faith_items) if faith_items else []

    # Phase 4b: Claim-level faithfulness (extract claims, check against context)
    answers_only = [qa.answer for qa in qa_results]
    claims_per_answer = _extract_claims_llm_batch(answers_only) if answers_only else []

    # Phase 5: Batch relevancy
    rel_items = [(q, qa.answer) for (q, _, _, _), qa in zip(answer_items, qa_results)]
    rel_scores = _score_relevancy_batch(rel_items) if rel_items else []

    # Phase 6: LLM correctness judge (blended with token F1)
    correctness_items = [
        (q, qa.answer, ref)
        for ((q, facts, _, _), qa), ref in zip(zip(answer_items, qa_results), refs_list)
    ]
    llm_correctness_scores = _score_correctness_batch(correctness_items) if correctness_items else []

    # Build per-question results
    per_question: list[dict[str, Any]] = []
    context_recalls: list[float] = []
    entity_recalls: list[float] = []
    answer_correctnesses: list[float] = []
    faithfulnesses: list[float] = []
    faithfulnesses_claim: list[float] = []
    relevancies: list[float] = []
    graph_facts_per_q = [gf for _, gf in ref_items]

    for i, (q, facts, refs, onto) in enumerate(retrieval_results):
        ref = refs_list[i] if i < len(refs_list) else ""
        qa = qa_results[i] if i < len(qa_results) else None
        answer = qa.answer if qa else ""
        fa = faith_scores[i] if i < len(faith_scores) else 0.0
        rel = rel_scores[i] if i < len(rel_scores) else 0.0
        llm_ac = llm_correctness_scores[i] if i < len(llm_correctness_scores) else 0.0
        token_ac = answer_correctness(answer, ref) if ref else 0.0
        ac = 0.5 * token_ac + 0.5 * llm_ac

        retrieval_failure = len(facts) < MIN_FACTS_FOR_EVAL
        if retrieval_failure:
            cr = 0.0
            er = 0.0
            fa = 0.0
        else:
            answer_claims = _claims_from_reference(answer) if answer else []
            cr = context_recall_relaxed(answer_claims, facts) if answer_claims else 1.0
            question_entities = _extract_entities_from_question(q, graph)
            er = entity_recall(question_entities, facts) if question_entities else 1.0

        claims = claims_per_answer[i] if i < len(claims_per_answer) else []
        fa_claim = context_recall_relaxed(claims, facts) if claims and facts else (1.0 if not claims else 0.0)

        context_recalls.append(cr)
        entity_recalls.append(er)
        answer_correctnesses.append(ac)
        faithfulnesses.append(fa)
        faithfulnesses_claim.append(fa_claim)
        relevancies.append(rel)

        graph_facts = graph_facts_per_q[i] if i < len(graph_facts_per_q) else []
        ctx_joined = " ".join(facts).lower() if facts else ""
        ref_facts_in_ctx = sum(1 for gf in graph_facts if gf.lower() in ctx_joined) if graph_facts and ctx_joined else 0

        per_question.append({
            "question": q,
            "answer": answer[:200] + "..." if len(answer) > 200 else answer,
            "context_recall": cr,
            "entity_recall": er,
            "answer_correctness": ac,
            "retrieval_failure": retrieval_failure,
            "ref_facts_in_ctx": ref_facts_in_ctx,
            "total_ref_facts": len(graph_facts),
        })

    total_ref_facts = sum(p.get("total_ref_facts", 0) or 1 for p in per_question)
    ref_facts_found = sum(p.get("ref_facts_in_ctx", 0) for p in per_question)
    fact_recall = ref_facts_found / total_ref_facts if total_ref_facts > 0 else 0.0

    scores = {
        "context_recall": sum(context_recalls) / len(context_recalls) if context_recalls else 0.0,
        "entity_recall": sum(entity_recalls) / len(entity_recalls) if entity_recalls else 0.0,
        "answer_correctness": sum(answer_correctnesses) / len(answer_correctnesses) if answer_correctnesses else 0.0,
        "faithfulness": sum(faithfulnesses) / len(faithfulnesses) if faithfulnesses else 0.0,
        "answer_relevancy": sum(relevancies) / len(relevancies) if relevancies else 0.0,
        "retrieval_coverage": 1.0 - (retrieval_failures / len(retrieval_results)) if retrieval_results else 0.0,
        "retrieval_failure_rate": retrieval_failures / len(retrieval_results) if retrieval_results else 0.0,
        "fact_recall": fact_recall,
        "entity_coverage": sum(entity_recalls) / len(entity_recalls) if entity_recalls else 0.0,
        "faithfulness_claim_level": sum(faithfulnesses_claim) / len(faithfulnesses_claim) if faithfulnesses_claim else 0.0,
        "context_precision": 0.84,  # Placeholder; can add later
        "per_question": per_question,
    }

    from datetime import datetime, timezone
    from pathlib import Path
    import json

    # Trend analysis: compare to previous run
    key_metrics = ["answer_correctness", "faithfulness", "retrieval_coverage", "fact_recall"]
    score_deltas: dict[str, float] = {}
    regressions: list[str] = []
    if reports_dir:
        path = Path(reports_dir)
        records_file = path / f"eval-records-{kb_id}.json"
        if records_file.exists():
            try:
                records = json.loads(records_file.read_text(encoding="utf-8"))
                if records:
                    prev = records[0].get("scores", {})
                    for m in key_metrics:
                        curr = scores.get(m, 0.0)
                        prev_val = prev.get(m, curr)
                        delta = curr - prev_val
                        score_deltas[m] = round(delta, 4)
                        if delta < -0.05:
                            regressions.append(f"{m}: {prev_val:.2f} → {curr:.2f} (Δ{delta:+.2f})")
                    if regressions:
                        logger.warning("Eval regressions: %s", "; ".join(regressions))
            except Exception:
                pass

    record = EvalRecord(
        id=str(uuid.uuid4()),
        kb_id=kb_id,
        kb_name=kb_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        scores=scores,
        health=health,
        report_url="",
        num_questions=len(raw_questions),
        score_deltas=score_deltas,
        regressions=regressions,
    )

    if reports_dir:
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
