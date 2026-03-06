"""CLI entry point for graph repair."""

import argparse
import json
import sys
from pathlib import Path

from ontology_builder.repair import RepairConfig, repair_graph
from ontology_builder.storage.graph_store import (
    get_ontology_graphs_dir,
    load_from_path,
    set_graph,
    save_to_path,
    save_to_path_with_metadata,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair ontology graph: link orphans, bridge components")
    parser.add_argument("path", nargs="?", help="Path to graph JSON or omit for --kb-id")
    parser.add_argument("--kb-id", help="Knowledge base ID (resolves path from ontology_graphs dir)")
    parser.add_argument("--dry-run", action="store_true", help="Report only, do not modify")
    parser.add_argument("--no-save", action="store_true", help="Do not persist (in-memory only)")
    parser.add_argument("--no-reasoning", action="store_true", help="Skip post-repair OWL 2 RL inference")
    parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold (default 0.75)")
    args = parser.parse_args()

    if args.kb_id:
        graphs_dir = get_ontology_graphs_dir()
        path = graphs_dir / f"{args.kb_id}.json"
        if not path.exists():
            print(f"Error: KB {args.kb_id} not found at {path}", file=sys.stderr)
            return 1
        kb_id = args.kb_id
    elif args.path:
        path = Path(args.path)
        if not path.exists():
            print(f"Error: Path {path} not found", file=sys.stderr)
            return 1
        kb_id = path.stem
    else:
        parser.error("Provide path or --kb-id")

    graph = load_from_path(path)
    config = RepairConfig(
        similarity_threshold=args.threshold,
        run_reasoning_after=not args.no_reasoning,
    )
    report = repair_graph(graph, config=config, dry_run=args.dry_run, kb_id=kb_id)

    print(f"Edges added: {report.edges_added}")
    print(f"Orphans linked: {report.orphans_linked}")
    print(f"Components bridged: {report.components_bridged}")
    print(f"Health before: {report.health_before.get('badge', 'N/A')} ({report.health_before.get('overall_score', 0)})")
    print(f"Health after: {report.health_after.get('badge', 'N/A')} ({report.health_after.get('overall_score', 0)})")

    if not args.dry_run and not args.no_save:
        set_graph(graph, document_subject=None)
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                save_to_path_with_metadata(
                    path,
                    name=meta.get("name", kb_id),
                    kb_id=kb_id,
                    description=meta.get("description", ""),
                    documents=meta.get("documents"),
                )
            except Exception:
                save_to_path(path)
        else:
            save_to_path(path)
        print(f"Saved to {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
