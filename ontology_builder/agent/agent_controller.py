"""Knowledge Agent: orchestrates multi-step KB exploration and Graph-of-Thought reasoning."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ontology_builder.agent.answer_synthesizer import synthesize_answer
from ontology_builder.agent.concept_extractor import extract_concepts
from ontology_builder.agent.graph_reasoner import ReasoningGraph
from ontology_builder.agent.kb_query_engine import KBQueryResult, query_kb
from ontology_builder.agent.memory_manager import MemoryManager
from ontology_builder.agent.ontology_gap_detector import detect_gaps
from ontology_builder.agent.ontology_questioner import generate_exploration_questions
from ontology_builder.agent.reasoning_logger import log_reasoning
from ontology_builder.qa.answer import QAResult
from ontology_builder.storage.graph_store import get_current_kb_id, get_ontology_language_for_kb

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from KnowledgeAgent.answer()."""

    answer: str = ""
    reasoning: str = ""
    sources: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    session_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    num_facts_used: int = 0


class KnowledgeAgent:
    """Orchestrates Graph-of-Thought reasoning and multi-step KB exploration."""

    def __init__(
        self,
        kb_id: str | None = None,
        assistant_mode: bool = False,
        max_exploration_steps: int = 5,
    ):
        self.kb_id = kb_id or get_current_kb_id()
        self.assistant_mode = assistant_mode
        self.max_exploration_steps = max_exploration_steps
        self.memory = MemoryManager(kb_id=self.kb_id)

    def answer(
        self,
        query: str,
        answer_language: str | None = None,
        session_id: str | None = None,
        on_step: Callable[[dict[str, Any]], None] | None = None,
    ) -> AgentResult:
        """Run multi-step KB exploration and synthesize answer.

        Flow:
        1. Extract concepts from query
        2. Build initial reasoning graph
        3. While not complete: generate questions -> query KB -> update graph -> detect gaps
        4. Synthesize final answer
        5. Log reasoning

        Args:
            query: User question.
            answer_language: Optional ISO 639-1 for answer language.
            session_id: Optional session ID for logging; generated if not provided.

        Returns:
            AgentResult with answer, reasoning, session_id, steps, gaps.
        """
        sid = session_id or str(uuid.uuid4())
        ontology_language = get_ontology_language_for_kb(self.kb_id)

        # 1. Extract concepts
        concepts = extract_concepts(query)
        if not concepts:
            concepts = [q.strip() for q in query.split() if len(q.strip()) > 2][:5]

        # 2. Build initial graph
        graph = ReasoningGraph(initial_concepts=concepts, max_steps=self.max_exploration_steps)

        # 3. Initial KB query with the original question
        initial_result = query_kb(query, top_k=15)
        graph.update(
            concepts=initial_result.concepts,
            relations=initial_result.relations,
            definitions=initial_result.definitions,
        )

        steps: list[dict[str, Any]] = [
            {
                "question": query,
                "answer": "\n".join(initial_result.facts[:5]) if initial_result.facts else "(no facts)",
                "concepts": initial_result.concepts,
                "relations": [
                    {"source": s, "relation": r, "target": t}
                    for s, r, t in initial_result.relations[:10]
                ],
            }
        ]
        if on_step:
            on_step(steps[0])

        previous_questions = [query]

        # 4. Exploration loop
        while not graph.complete():
            gaps_current = detect_gaps(query, graph)
            gaps_serializable = [
                {
                    "gap_type": g.gap_type,
                    "subject": g.subject,
                    "relation": g.relation,
                    "target": g.target,
                    "description": g.description,
                }
                for g in gaps_current
            ]
            questions = generate_exploration_questions(
                query,
                graph,
                previous_questions=previous_questions,
                steps=steps,
                gaps=gaps_serializable,
                ontology_language=ontology_language,
            )
            if not questions:
                break

            for q in questions:
                if graph.complete():
                    break
                prev = list(previous_questions)
                kb_result = query_kb(q, top_k=12)
                graph.update(
                    concepts=kb_result.concepts,
                    relations=kb_result.relations,
                    definitions=kb_result.definitions,
                )
                step_dict = {
                    "question": q,
                    "answer": "\n".join(kb_result.facts[:5]) if kb_result.facts else "(no facts)",
                    "concepts": kb_result.concepts,
                    "relations": [
                        {"source": s, "relation": r, "target": t}
                        for s, r, t in kb_result.relations[:10]
                    ],
                }
                steps.append(step_dict)
                if on_step:
                    on_step(step_dict)
                previous_questions.append(q)

        # 5. Detect gaps
        gaps = detect_gaps(query, graph)
        gaps_serializable = [
            {
                "gap_type": g.gap_type,
                "subject": g.subject,
                "relation": g.relation,
                "target": g.target,
                "description": g.description,
            }
            for g in gaps
        ]

        # 6. Synthesize answer
        qa_result = synthesize_answer(query, graph, answer_language=answer_language)
        context_lines = [ln for ln in graph.to_context_string().strip().split("\n") if ln.strip()]

        # 7. Log reasoning
        log_reasoning(
            session_id=sid,
            query=query,
            steps=steps,
            graph=graph,
            gaps=gaps,
            answer=qa_result.answer,
            reasoning=qa_result.reasoning,
        )

        # 8. Update memory
        self.memory.add_to_session(query, qa_result.answer, qa_result.reasoning)
        self.memory.set_session_reasoning_graph(graph)

        return AgentResult(
            answer=qa_result.answer,
            reasoning=qa_result.reasoning,
            sources=context_lines,
            source_refs=qa_result.sources,
            session_id=sid,
            steps=steps,
            gaps=gaps_serializable,
            num_facts_used=qa_result.num_facts_used,
        )
