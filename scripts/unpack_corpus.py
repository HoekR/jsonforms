#!/usr/bin/env python3
"""Unpack a published formdef corpus into formdefs/ and document files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORPUS_KIND = "formdef-corpus"


def load_corpus(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("kind") != CORPUS_KIND or not isinstance(data.get("documents"), list):
        raise SystemExit(f"{path} is not a formdef-corpus")
    return data


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="corpus JSON from Publish")
    parser.add_argument("--formdefs", type=Path, default=Path("formdefs"))
    parser.add_argument("--documents", type=Path, default=Path("published"))
    parser.add_argument("--lists", type=Path, help="write lists.json here")
    args = parser.parse_args(argv)

    data = load_corpus(args.corpus)
    n_def = 0
    for key, defn in (data.get("formdefs") or {}).items():
        formkey = (defn or {}).get("formkey") or key
        if not formkey:
            continue
        write_json(args.formdefs / f"{formkey}.json", defn)
        n_def += 1

    n_doc = 0
    for doc in data.get("documents") or []:
        if not doc or not doc.get("form") or doc.get("form") == "formdef":
            continue
        write_json(args.documents / f"{doc['form']}.json", doc)
        n_doc += 1

    if args.lists is not None:
        write_json(args.lists, data.get("lists") or {})

    print(f"published {data.get('published')}")
    print(f"wrote {n_def} formdef(s) → {args.formdefs}/")
    print(f"wrote {n_doc} document(s) → {args.documents}/")
    if args.lists is not None:
        print(f"wrote lists → {args.lists}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
