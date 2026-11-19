#!/usr/bin/env python3
"""Pack formdefs, lists, and sample/published documents into search-data.js."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpusutil import ROOT, collect_documents, load_formdefs, load_lists

payload = {
    "formdefs": load_formdefs(),
    "lists": load_lists(),
    "documents": collect_documents(),
}
dest = ROOT / "search-data.js"
with dest.open("w", encoding="utf-8") as fh:
    fh.write("window.SEARCH_DATA = ")
    json.dump(payload, fh, ensure_ascii=False)
    fh.write(";\n")
print(f"wrote {dest} ({len(payload['documents'])} documents)")
