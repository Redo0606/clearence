"""
Infer an optimal, bounded set of web search queries from an OntologyGraph.

Strategy
--------
1. Collect all nodes with their vote_count and degree.
2. Score = 0.6 * norm(vote_count) + 0.4 * norm(degree)
3. Take top-K nodes where K = ceil(sqrt(N)) capped at max_queries (default 20).
4. Batch-infer queries via LLM using high-quality graph context (descriptions,
   relations, types). Fallback to rule-based DuckDuckGo-optimized queries.

DuckDuckGo optimization: natural-language phrases ("definition", "concept",
"explained") yield better results than bare entity names.
"""

import json
import logging
import math

from ontology_builder.llm.client import complete
from ontology_builder.llm.json_repair import repair_json

logger = logging.getLogger(__name__)

DEFAULT_MAX_QUERIES = 20
_MAX_CONTEXT_CHARS = 12000  # larger context for high-confidence inference
_RELATION_SUFFIX = " relationship"

# Prompts use .format() — {{ and }} become literal braces in JSON examples
QUERY_INFER_SYSTEM = """\
You are an expert at generating web search queries that retrieve high-quality, authoritative content for ontology enrichment.

Your task: Given an ontology graph (concepts, relations, descriptions), produce natural-sounding search queries that a human would type into DuckDuckGo to find definitions, explanations, and conceptual content.

CRITICAL — DOMAIN-SPECIFIC QUERIES:
- Infer the ontology's domain/topic from node names, descriptions, and relations (e.g. League of Legends, Pokémon, medicine, finance).
- EVERY query MUST include the domain to avoid irrelevant results. Generic terms like "champion", "ability", "item" match many games—always disambiguate.
- Examples: "League of Legends champion concept" NOT "champion concept explained in games"; "LoL Summoner's Rift map" NOT "Rift map overview".
- If the domain is a game: include the game name (e.g. "League of Legends", "LoL", "Pokémon"). If it's a technical domain: include the framework/product name.

PRIORITIZE high-confidence nodes: Each node has confidence_score (0–1), vote_count, and degree. Favor nodes with higher confidence_score and vote_count.

QUERY STYLE — natural and domain-anchored:
- 5–14 words per query. Include domain + concept + search-intent.
- Search-intent terms: definition, concept, explained, overview, how does, what is, relationship between
- For relations: "[domain] X and Y relationship", "how X relates to Y in [domain]"

TARGET SOURCES: Wikipedia, official wikis, documentation, glossaries, .edu, authoritative guides.

Output ONLY valid JSON. No markdown, no code fences, no commentary.
Return a JSON object with a "queries" key containing an array of strings.
Example for League of Legends: {{ "queries": ["League of Legends champion definition", "LoL Summoner's Rift map explained", "what is ability power in League of Legends"] }}
"""

QUERY_INFER_USER = """\
From this ontology graph context, generate up to {max_queries} natural, domain-specific web search queries.

RULES:
1. Infer the domain from node names and descriptions (e.g. League of Legends, Pokémon).
2. EVERY query MUST include the domain name to avoid irrelevant results.
3. Prioritize nodes with higher confidence_score and vote_count.
{domain_instruction}

{context_json}

Reply with a JSON object containing a "queries" field with a list of strings.
"""


# Domain hints: node-name patterns -> search-friendly domain string
_DOMAIN_HINTS = [
    (["champion", "summoner", "rift", "lol", "league of legends", "ability power", "summoner spell"], "League of Legends"),
    (["pokemon", "pokémon", "pikachu", "trainer", "gym", "evolution"], "Pokémon"),
    (["minecraft", "block", "mob", "biome", "crafting"], "Minecraft"),
]


def _infer_domain_hint(graph, kb_path=None) -> str:
    """Infer domain from graph nodes and optional KB metadata. Returns empty string if unknown."""
    try:
        import orjson
        from pathlib import Path
    except ImportError:
        return ""

    # 1. Try KB metadata (name, description)
    if kb_path:
        path = Path(kb_path) if not isinstance(kb_path, Path) else kb_path
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = orjson.loads(meta_path.read_bytes())
                name = (meta.get("name") or "").lower()
                desc = (meta.get("description") or "").lower()
                combined = f"{name} {desc}"
                for keywords, domain in _DOMAIN_HINTS:
                    if any(kw in combined for kw in keywords):
                        return domain
            except (OSError, orjson.JSONDecodeError, TypeError):
                pass

    # 2. Infer from node names
    nx_graph = graph.get_graph()
    all_names = " ".join(str(n).lower() for n in nx_graph.nodes())[:2000]
    for keywords, domain in _DOMAIN_HINTS:
        if sum(1 for kw in keywords if kw in all_names) >= 2:
            return domain
    return ""


def _gather_node_context(nx_graph, node: str, data: dict, score: float) -> dict:
    """Build rich context for a node: description, type, relations, neighbors, confidence."""
    desc = (data.get("description") or "")[:300]
    etype = data.get("type", "Class")
    kind = data.get("kind", "class")
    vote_count = data.get("vote_count", 1)
    degree = nx_graph.degree(node)
    out_edges = list(nx_graph.out_edges(node, data=True))
    in_edges = list(nx_graph.in_edges(node, data=True))
    neighbors = set()
    relations = []
    for u, v, ed in out_edges[:8]:
        rel = ed.get("relation", "related_to")
        vc = ed.get("vote_count", 1)
        relations.append(f"{rel}({v}) [votes:{vc}]")
        neighbors.add(v)
    for u, v, ed in in_edges[:4]:
        rel = ed.get("relation", "related_to")
        relations.append(f"{u} --{rel}->")
        neighbors.add(u)
    return {
        "name": node,
        "description": desc,
        "type": etype,
        "kind": kind,
        "vote_count": vote_count,
        "degree": degree,
        "confidence_score": round(score, 2),
        "relations": relations[:10],
        "neighbors": list(neighbors)[:6],
    }


def _infer_queries_llm(contexts: list[dict], max_queries: int, domain_hint: str = "") -> list[str] | None:
    """Batch-infer search queries via LLM. Returns None on failure."""
    try:
        context_json = json.dumps(contexts, indent=2)[:_MAX_CONTEXT_CHARS]
        domain_instruction = (
            f'4. DETECTED DOMAIN: "{domain_hint}" — include this in EVERY query.'
            if domain_hint
            else "4. If the ontology is clearly about a specific game, product, or domain, infer it and include it in every query."
        )
        user = QUERY_INFER_USER.format(
            max_queries=max_queries,
            domain_instruction=domain_instruction,
            context_json=context_json,
        )

        raw = complete(
            system=QUERY_INFER_SYSTEM,
            user=user,
            temperature=0.15,
            max_tokens=800,
        )

        data = repair_json(raw or "{}")
        raw_queries: list = []
        if isinstance(data, list):
            raw_queries = data
        elif isinstance(data, dict):
            for key in ("queries", "search_queries", "query_list"):
                if key in data and isinstance(data[key], list):
                    raw_queries = data[key]
                    break
        if not raw_queries:
            return None

        queries = [str(q).strip() for q in raw_queries if q and str(q).strip()]
        if not queries:
            return None

        # Ensure every query has search-intent terms for better DuckDuckGo results
        search_terms = ("definition", "concept", "explained", "overview", "what is", "meaning of", "how does", "relationship", "difference")
        out = []
        for q in queries[:max_queries]:
            q_lower = q.lower()
            if not any(t in q_lower for t in search_terms):
                q = "what is " + q if len(q.split()) <= 2 else (q + " definition")
            out.append(q)
        logger.info("[QueryPlanner] LLM inferred %d queries", len(out))
        return out
    except Exception as e:
        logger.warning("[QueryPlanner] LLM inference failed, using rule-based: %s", e)
        return None


def _plan_queries_rule_based(nx_graph, top_nodes: list[str], cap: int) -> list[str]:
    """Fallback: rule-based DuckDuckGo-optimized queries."""
    queries = []
    seen = set()

    def _add(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    for node in top_nodes:
        _add(f"{node} definition")
        best_edge = max(
            nx_graph.out_edges(node, data=True),
            key=lambda e: e[2].get("vote_count", 0),
            default=None,
        )
        if best_edge:
            src, tgt, data = best_edge
            rel = data.get("relation", "related to")
            _add(f"{src} {rel} {tgt}{_RELATION_SUFFIX}")

    return queries[:cap]


def plan_queries(graph, max_queries=None, use_llm: bool = True, kb_path=None):
    """
    Args:
        graph      : OntologyGraph
        max_queries: int | None — hard cap; defaults to min(ceil(sqrt(N)), 20)
        use_llm    : bool — if True, batch-infer via LLM; else rule-based only
        kb_path    : Path | str | None — if provided, used to infer domain from metadata

    Returns:
        list[str] — deduplicated, domain-specific search query strings
    """
    nx_graph = graph.get_graph()
    nodes = list(nx_graph.nodes(data=True))
    N = len(nodes)
    if N == 0:
        return []

    cap = max_queries or min(math.ceil(math.sqrt(N)), DEFAULT_MAX_QUERIES)

    # --- score nodes ---
    votes = [d.get("vote_count", 1) for _, d in nodes]
    degrees = [nx_graph.degree(n) for n, _ in nodes]
    max_v = max(votes) or 1
    max_d = max(degrees) or 1
    scored = [
        (n, 0.6 * (v / max_v) + 0.4 * (deg / max_d))
        for (n, d), v, deg in zip(nodes, votes, degrees)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_nodes_with_scores = [(n, s) for n, s in scored[:cap]]
    top_nodes = [n for n, _ in top_nodes_with_scores]

    # --- gather high-quality context (prioritize high-confidence nodes) ---
    contexts = []
    total_chars = 0
    for node, score in top_nodes_with_scores:
        data = dict(nx_graph.nodes[node])
        ctx = _gather_node_context(nx_graph, node, data, score)
        contexts.append(ctx)
        total_chars += len(json.dumps(ctx))
        if total_chars >= _MAX_CONTEXT_CHARS:
            break

    # --- infer domain hint for query disambiguation ---
    domain_hint = _infer_domain_hint(graph, kb_path)
    if domain_hint:
        logger.info("[QueryPlanner] Inferred domain: %s", domain_hint)

    # --- batch-infer via LLM or fallback ---
    if use_llm and contexts:
        queries = _infer_queries_llm(contexts, cap, domain_hint=domain_hint)
        if queries:
            return queries

    # Rule-based: prepend domain when known
    base_queries = _plan_queries_rule_based(nx_graph, top_nodes, cap)
    if domain_hint:
        return [f"{domain_hint} {q}" if domain_hint.lower() not in q.lower() else q for q in base_queries]
    return base_queries
