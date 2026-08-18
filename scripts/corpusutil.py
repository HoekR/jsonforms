#!/usr/bin/env python3
"""Shared helpers: gather searchable documents and an ES mapping from formdefs."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEXT_FALLBACK = {
    "persoon": ("biografie", "functies"),
    "instelling": ("taak", "organisatie"),
    "autopsie": ("text", "titel"),
    "tekst": ("tekst", "titel"),
}

SKIP_FORMS = {"formdef", "formdef_field"}
HTML_TAG = re.compile(r"<[^>]+>")


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_formdefs(root: Path = ROOT) -> dict:
    formdefs = {}
    folder = root / "formdefs"
    for name in os.listdir(folder):
        if not name.endswith(".json") or name == "index.json":
            continue
        data = load_json(folder / name)
        formdefs[data["formkey"]] = data
    return formdefs


def load_lists(root: Path = ROOT) -> dict:
    lists = load_json(root / "lists.json")
    meta = root / "lists-meta.json"
    if meta.exists():
        lists.update(load_json(meta))
    return lists


def strip_html(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)
    return HTML_TAG.sub(" ", value)


def guess_form(path: Path, data: dict) -> str | None:
    if data.get("form"):
        return data["form"]
    stem = path.stem
    for suffix in ("-full", "-draft"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem if stem else None


def ensure_document(path: Path, data: dict) -> dict | None:
    doc = dict(data)
    form = guess_form(path, doc)
    if not form or form in SKIP_FORMS:
        return None
    doc["form"] = form
    if not (doc.get("text") or "").strip():
        for key in TEXT_FALLBACK.get(form, ()):
            if doc.get(key):
                doc["text"] = strip_html(doc[key]).strip()
                break
        else:
            doc["text"] = strip_html(doc.get("titel") or "")
    return doc


def collect_documents(root: Path = ROOT) -> list[dict]:
    docs = []
    seen = set()
    folders = [root / "published", root / "samples"]
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            data = load_json(path)
            doc = ensure_document(path, data)
            if not doc:
                continue
            key = doc.get("obj_name") or f"{doc['form']}:{path.name}"
            if key in seen:
                continue
            seen.add(key)
            docs.append(doc)
    return docs


def elasticsearch_mapping(formdefs: dict) -> dict:
    name_keys = {
        defn.get("namefield")
        for defn in formdefs.values()
        if defn.get("level") == "main" and defn.get("namefield")
    }
    properties = {
        "form": {"type": "keyword"},
        "text": {"type": "text"},
    }
    for defn in formdefs.values():
        for field in defn.get("fields") or []:
            key = field.get("key")
            if not key or key == "text" or key in properties:
                continue
            ftype = field.get("type")
            if key in name_keys:
                properties[key] = {"type": "text", "fields": {"raw": {"type": "keyword"}}}
            elif ftype in ("list", "choice"):
                properties[key] = {"type": "keyword"}
            elif ftype == "bool":
                properties[key] = {"type": "boolean"}
            elif ftype == "form":
                properties[key] = (
                    {"type": "nested"} if field.get("repeater") else {"type": "object", "enabled": True}
                )
            else:
                properties[key] = {"type": "text"}
    return {"mappings": {"properties": properties}}
