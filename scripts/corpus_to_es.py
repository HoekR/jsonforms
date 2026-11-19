#!/usr/bin/env python3
"""Turn a published corpus (or the repo samples) into an ES mapping + bulk file.

Does not talk to Elasticsearch. Load with:

  curl -X PUT localhost:9200/jsonforms -H 'Content-Type: application/json' --data @es/mapping.json
  curl -X POST localhost:9200/_bulk -H 'Content-Type: application/x-ndjson' --data-binary @es/bulk.ndjson
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpusutil import (
    ROOT,
    SKIP_FORMS,
    collect_documents,
    elasticsearch_mapping,
    load_formdefs,
    load_lists,
)


def load_corpus(path: Path) -> tuple[dict, dict, list]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("kind") != "formdef-corpus":
        raise SystemExit(f"{path} is not a formdef-corpus")
    docs = [doc for doc in data.get("documents") or [] if doc and doc.get("form") not in SKIP_FORMS]
    return data.get("formdefs") or {}, data.get("lists") or {}, docs


def doc_id(doc: dict, index: int) -> str:
    return str(doc.get("obj_name") or doc.get("id") or f"{doc.get('form', 'doc')}-{index}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", type=Path, help="corpus JSON from Publish")
    parser.add_argument("--out", type=Path, default=ROOT / "es")
    parser.add_argument("--index", default="jsonforms")
    args = parser.parse_args(argv)

    if args.corpus:
        formdefs, _lists, documents = load_corpus(args.corpus)
        if not formdefs:
            formdefs = load_formdefs()
    else:
        formdefs, _lists, documents = load_formdefs(), load_lists(), collect_documents()

    args.out.mkdir(parents=True, exist_ok=True)
    mapping = elasticsearch_mapping(formdefs)
    (args.out / "mapping.json").write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = []
    for i, doc in enumerate(documents):
        lines.append(json.dumps({"index": {"_index": args.index, "_id": doc_id(doc, i)}}))
        lines.append(json.dumps(doc, ensure_ascii=False))
    (args.out / "bulk.ndjson").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print(f"wrote {args.out / 'mapping.json'}")
    print(f"wrote {args.out / 'bulk.ndjson'} ({len(documents)} documents)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
