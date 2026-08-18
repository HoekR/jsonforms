#!/usr/bin/env python3
"""Pack converted jsonforms documents into a formdef-corpus for search.html.

  python3 scripts/pack_corpus.py converted/emigratie
  python3 scripts/pack_corpus.py converted/emigratie --out converted/emigratie-corpus.json
  python3 scripts/pack_corpus.py converted/emigratie --forms persoon,instelling,autopsie,tekst

Does not load the pack into the editor (one document per form there).
Open search.html → Load corpus.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpusutil import ROOT, SKIP_FORMS, load_formdefs, load_json, load_lists

SKIP_NAMES = {"_formdefs.json", "_lists.json", "_stats.json", "index.json"}


def iter_docs(folder: Path):
    for path in sorted(folder.rglob("*.json")):
        if path.name in SKIP_NAMES:
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        form = data.get("form")
        if not form or form in SKIP_FORMS:
            continue
        yield data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Directory of converted documents")
    parser.add_argument(
        "--out",
        type=Path,
        help="Corpus JSON (default: <folder>-corpus.json next to the folder)",
    )
    parser.add_argument("--forms", help="Comma-separated formkeys to keep")
    args = parser.parse_args(argv)

    folder = args.folder
    if not folder.is_dir():
        raise SystemExit(f"{folder} is not a directory")

    want = {item.strip() for item in args.forms.split(",")} if args.forms else None
    documents = []
    for doc in iter_docs(folder):
        if want and doc["form"] not in want:
            continue
        documents.append(doc)

    dest = args.out
    if dest is None:
        dest = folder.parent / f"{folder.name}-corpus.json"

    pack = {
        "kind": "formdef-corpus",
        "published": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "formdefs": load_formdefs(),
        "lists": load_lists(),
        "documents": documents,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(pack, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {dest} ({len(documents)} documents, {dest.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
