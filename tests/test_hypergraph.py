"""Tests for OG-RAG hypergraph construction."""

from ontology_builder.storage.hypergraph import (
    HyperGraph,
    build_hypergraph,
    flatten_factual_block,
)


def test_flatten_factual_block():
    block = {
        "subject": "Dog",
        "attributes": [
            {"relation": "subClassOf", "target": "Animal", "key": "Dog: subClassOf", "value": "Animal", "full": "Dog: subClassOf -> Animal"},
            {"relation": "has", "target": "Tail", "key": "Dog: has", "value": "Tail", "full": "Dog: has -> Tail"},
        ],
    }
    triples = flatten_factual_block(block)
    assert len(triples) == 2
    assert triples[0] == ("Dog: subClassOf", "Animal", "Dog: subClassOf -> Animal")


def test_flatten_empty_block():
    block = {"subject": "X", "attributes": []}
    assert flatten_factual_block(block) == []


def test_build_hypergraph_basic():
    blocks = [
        {
            "subject": "Dog",
            "attributes": [
                {"relation": "subClassOf", "target": "Animal", "key": "Dog: subClassOf", "value": "Animal", "full": "Dog: subClassOf -> Animal"},
            ],
        },
        {
            "subject": "Cat",
            "attributes": [
                {"relation": "subClassOf", "target": "Animal", "key": "Cat: subClassOf", "value": "Animal", "full": "Cat: subClassOf -> Animal"},
            ],
        },
    ]
    hg = build_hypergraph(blocks)
    assert len(hg.nodes) == 2
    assert len(hg.edges) == 2


def test_build_hypergraph_shared_nodes():
    """Two blocks sharing the same (key, value) pair should reuse the hypernode."""
    blocks = [
        {
            "subject": "A",
            "attributes": [
                {"key": "A: rel", "value": "B", "full": "A rel B"},
                {"key": "A: type", "value": "C", "full": "A type C"},
            ],
        },
        {
            "subject": "D",
            "attributes": [
                {"key": "A: rel", "value": "B", "full": "A rel B"},
            ],
        },
    ]
    hg = build_hypergraph(blocks)
    assert len(hg.nodes) == 3
    assert len(hg.edges) == 2


def test_build_hypergraph_empty():
    hg = build_hypergraph([])
    assert len(hg.nodes) == 0
    assert len(hg.edges) == 0


def test_hypernode_add_returns_same_index():
    hg = HyperGraph()
    i1 = hg.add_node("k", "v")
    i2 = hg.add_node("k", "v")
    assert i1 == i2
    assert len(hg.nodes) == 1
