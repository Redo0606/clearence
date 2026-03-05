"""Tests for evaluation metrics."""

from ontology_builder.evaluation.metrics import (
    PipelineReport,
    PipelineTimer,
    answer_correctness,
    context_recall,
    entity_recall,
    ontology_quality,
)


def test_ontology_quality_perfect():
    result = ontology_quality(
        predicted_classes={"A", "B"},
        reference_classes={"A", "B"},
        predicted_instances={"x"},
        reference_instances={"x"},
        predicted_relations={("A", "rel", "B")},
        reference_relations={("A", "rel", "B")},
        graph_num_edges=1,
        graph_num_nodes=3,
    )
    assert result["class_metrics"]["f1"] == 1.0
    assert result["instance_metrics"]["f1"] == 1.0
    assert result["relation_metrics"]["f1"] == 1.0
    assert result["overall_f1"] == 1.0


def test_ontology_quality_partial():
    result = ontology_quality(
        predicted_classes={"A", "B", "C"},
        reference_classes={"A", "B"},
        predicted_instances=set(),
        reference_instances={"x"},
        predicted_relations=set(),
        reference_relations={("A", "rel", "B")},
    )
    assert result["class_metrics"]["precision"] < 1.0
    assert result["class_metrics"]["recall"] == 1.0
    assert result["instance_metrics"]["f1"] == 0.0


def test_ontology_quality_empty():
    result = ontology_quality(
        predicted_classes=set(), reference_classes=set(),
        predicted_instances=set(), reference_instances=set(),
        predicted_relations=set(), reference_relations=set(),
    )
    assert result["overall_f1"] == 1.0


def test_context_recall():
    gt_claims = ["dogs are animals", "cats are pets"]
    context = ["dogs are animals and live in houses", "birds can fly"]
    assert context_recall(gt_claims, context) == 0.5


def test_context_recall_empty():
    assert context_recall([], ["anything"]) == 1.0


def test_entity_recall():
    gt_entities = {"dog", "cat", "bird"}
    context = ["The dog chased the cat", "Fish swim"]
    assert entity_recall(gt_entities, context) == 2 / 3


def test_answer_correctness_identical():
    assert answer_correctness("the cat sat", "the cat sat") == 1.0


def test_answer_correctness_partial():
    score = answer_correctness("the cat sat on the mat", "the dog sat on the mat")
    assert 0.5 < score < 1.0


def test_answer_correctness_empty():
    assert answer_correctness("", "") == 1.0
    assert answer_correctness("hello", "") == 0.0


def test_pipeline_report_to_dict():
    report = PipelineReport(
        document_path="/tmp/doc.pdf",
        total_chunks=5,
        total_classes=10,
        total_relations=20,
        elapsed_seconds=3.14,
    )
    d = report.to_dict()
    assert d["document_path"] == "/tmp/doc.pdf"
    assert d["totals"]["classes"] == 10
    assert d["elapsed_seconds"] == 3.14


def test_pipeline_timer():
    import time
    with PipelineTimer() as t:
        time.sleep(0.01)
    assert t.elapsed > 0
