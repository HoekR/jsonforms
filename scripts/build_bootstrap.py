#!/usr/bin/env python3
"""Pack formdefs, lists, and the draft document into bootstrap.js (for file://)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

formdefs = {}
for name in os.listdir(os.path.join(ROOT, "formdefs")):
    if not name.endswith(".json") or name == "index.json":
        continue
    with open(os.path.join(ROOT, "formdefs", name), encoding="utf-8") as fh:
        data = json.load(fh)
    formdefs[data["formkey"]] = data

with open(os.path.join(ROOT, "lists.json"), encoding="utf-8") as fh:
    lists = json.load(fh)

meta_lists = os.path.join(ROOT, "lists-meta.json")
if os.path.exists(meta_lists):
    with open(meta_lists, encoding="utf-8") as fh:
        lists.update(json.load(fh))

with open(os.path.join(ROOT, "samples", "persoon-draft.json"), encoding="utf-8") as fh:
    draft = json.load(fh)

payload = {"formdefs": formdefs, "lists": lists, "draft": draft}
dest = os.path.join(ROOT, "bootstrap.js")
with open(dest, "w", encoding="utf-8") as fh:
    fh.write("window.BOOTSTRAP = ")
    json.dump(payload, fh, ensure_ascii=False)
    fh.write(";\n")
print("wrote", dest)
