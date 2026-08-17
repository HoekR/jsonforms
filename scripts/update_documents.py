#!/usr/bin/env python3
"""Rewrite document JSON after a formdef field is renamed, typed, or removed.

Example:
  python3 scripts/update_documents.py \\
    --from formdefs/persoon.json --to formdefs/persoon.json \\
    --rename periode=leefjaren --dry-run samples/*.json

  python3 scripts/update_documents.py \\
    --from old/persoon.json --to formdefs/persoon.json --write samples/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def parse_renames(items: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"rename must be old=new, got {item!r}")
        old, new = item.split("=", 1)
        out[old.strip()] = new.strip()
    return out


def diff_formdefs(old_def: dict, new_def: dict, extra: dict[str, str]) -> dict:
    old_fields = old_def.get("fields") or []
    new_fields = new_def.get("fields") or []
    old_keys = [field["key"] for field in old_fields]
    new_keys = [field["key"] for field in new_fields]
    old_set, new_set = set(old_keys), set(new_keys)
    renames = dict(extra)

    for old_field, new_field in zip(old_fields, new_fields):
        src, dest = old_field["key"], new_field["key"]
        if src == dest or src in new_set or dest in old_set or src in renames:
            continue
        # Same slot, old key gone, new key is new → treat as rename.
        renames[src] = dest

    removed = [key for key in old_keys if key not in new_set and key not in renames]
    type_changes = []
    old_by_key = {field["key"]: field for field in old_fields}
    for field in new_fields:
        previous = next((k for k, v in renames.items() if v == field["key"]), field["key"])
        prev = old_by_key.get(previous)
        if not prev:
            continue
        if prev.get("type") != field.get("type") or bool(prev.get("repeater")) != bool(
            field.get("repeater")
        ):
            type_changes.append({"key": field["key"], "from": prev, "to": field})

    return {
        "formkey": new_def.get("formkey"),
        "renames": renames,
        "removed": removed,
        "typeChanges": type_changes,
        "fields": new_fields,
    }


def coerce_value(value, field):
    if value is None:
        ftype = field.get("type")
        if ftype == "bool":
            return False
        if ftype == "list" or field.get("repeater"):
            return []
        if ftype == "form":
            return [] if field.get("repeater") else {}
        return "" if ftype in ("text", "choice") else value

    ftype = field.get("type")
    if ftype == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, list):
            return any(item is True or item == "true" for item in value)
        return value in (True, "true", "yes")
    if ftype == "choice":
        if isinstance(value, list):
            return value[0] if value else ""
        return "" if value is None else str(value)
    if ftype == "list" or field.get("repeater"):
        if isinstance(value, list):
            return value
        if value in ("", None):
            return []
        return [value]
    if ftype == "form":
        if field.get("repeater"):
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
            return []
        if isinstance(value, list):
            return value[0] if value else {}
        if isinstance(value, dict):
            return value
        return {}
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def migrate_document(doc: dict, plan: dict, keep_unknown=True, keep_removed=False):
    if doc.get("form") and plan.get("formkey") and doc["form"] != plan["formkey"]:
        return doc, []

    changes = []
    skip = {"form", "text"}
    incoming = {}
    for key, value in doc.items():
        if key in skip:
            continue
        dest = plan["renames"].get(key, key)
        if dest != key:
            changes.append({"op": "rename", "from": key, "to": dest})
        incoming[dest] = value

    next_doc = {"form": doc.get("form"), "text": doc.get("text")}
    known = {field["key"] for field in plan["fields"]}
    for field in plan["fields"]:
        key = field["key"]
        if key not in incoming:
            continue
        before = incoming[key]
        after = coerce_value(before, field)
        next_doc[key] = after
        if before != after:
            changes.append({"op": "coerce", "key": key, "type": field.get("type")})

    for key, value in incoming.items():
        if key in next_doc:
            continue
        if key in plan["removed"] and not keep_removed:
            changes.append({"op": "drop", "key": key})
            continue
        if keep_unknown or key in known or keep_removed:
            next_doc[key] = value

    return next_doc, changes


def iter_docs(paths: list[Path]):
    for path in paths:
        if path.is_dir():
            yield from sorted(path.glob("*.json"))
        else:
            yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_formdef", type=Path, help="previous formdef JSON")
    parser.add_argument("--to", dest="to_formdef", type=Path, required=True, help="new formdef JSON")
    parser.add_argument("--rename", action="append", default=[], help="old=new (repeatable)")
    parser.add_argument("--write", action="store_true", help="overwrite files (default is dry-run)")
    parser.add_argument("--keep-removed", action="store_true")
    parser.add_argument("--drop-unknown", action="store_true")
    parser.add_argument("paths", nargs="+", type=Path, help="document JSON files or directories")
    args = parser.parse_args(argv)

    new_def = load_json(args.to_formdef)
    old_def = load_json(args.from_formdef) if args.from_formdef else {"fields": new_def.get("fields")}
    plan = diff_formdefs(old_def, new_def, parse_renames(args.rename))

    print("form", plan["formkey"])
    print("renames", plan["renames"] or "—")
    print("removed", plan["removed"] or "—")
    print(
        "type changes",
        [item["key"] for item in plan["typeChanges"]] or "—",
    )

    n = 0
    for path in iter_docs(args.paths):
        doc = load_json(path)
        updated, changes = migrate_document(
            doc,
            plan,
            keep_unknown=not args.drop_unknown,
            keep_removed=args.keep_removed,
        )
        if not changes:
            continue
        n += 1
        print(f"\n{path}")
        for change in changes:
            print(" ", change)
        if args.write:
            path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not args.write:
        print("\ndry-run; pass --write to save")
    print(f"\n{n} document(s) would be updated" if not args.write else f"\n{n} document(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
