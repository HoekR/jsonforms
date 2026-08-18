#!/usr/bin/env python3
"""Convert IngForms XML (content_repository.zip) to jsonforms documents.

Formdefs in the zip describe fields. Each data XML file becomes:

  { "form": "<root tag>", "text": "...", "obj_name": "...", ...islands }

`text` is filled from a transcription-like field when present (text, tekst,
transcriptie, biografie, …). Other non-empty fields become islands.

The zip is not in this repo. Output defaults to converted/ (gitignored).

  python3 scripts/convert_ingforms_xml.py --zip /path/to/content_repository.zip
  python3 scripts/convert_ingforms_xml.py --zip … --project emigratie
  python3 scripts/convert_ingforms_xml.py --zip … --limit 20 --indent
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent

TEXT_CANDIDATES = (
    "text",
    "tekst",
    "transcriptie",
    "biografie",
    "regest",
    "omschrijving",
    "inhoud",
    "contents",
    "samenvatting",
    "organisatie",
    "taak",
    "doelstelling",
)

SKIP_ROOTS = {"formdef", "ingformslist", "html", "xml"}
HTML_BR = re.compile(r"<br\s*/?>", re.I)
HTML_P = re.compile(r"</p>", re.I)
HTML_TAG = re.compile(r"<[^>]+>")


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def child(el: ET.Element, tag: str) -> ET.Element | None:
    for item in list(el):
        if local(item.tag) == tag:
            return item
    return None


def children_named(el: ET.Element, tag: str) -> list[ET.Element]:
    return [item for item in list(el) if local(item.tag) == tag]


def leaf_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    raw = "".join(el.itertext()) if len(el) else (el.text or "")
    return html.unescape(raw).strip()


def wiki_to_markdown(text: str) -> str:
    """Turn IngForms wiki marks into Markdown record links."""

    def labeled(match: re.Match) -> str:
        ident = match.group(1).strip()
        label = match.group(2).strip()
        return f"[{label}](ref:{ident})"

    def bare(match: re.Match) -> str:
        ident = match.group(2).strip()
        label = re.sub(r"^\d+", "", ident).strip() or ident
        return f"{match.group(1)}[{label}](ref:{ident})"

    text = re.sub(r"##([^#\n]+)#([^#\n]+)##", labeled, text)
    text = re.sub(r"(^|[^#])#([A-Za-z0-9][^#\n]{0,120}?)#", bare, text)
    return text


def relation_ref(path: str) -> str:
    """IngForms /data/.../01PvdA → instelling:01PvdA (or ref:id)."""
    raw = (path or "").strip()
    if not raw:
        return raw
    if re.match(r"^(ref|persoon|instelling|autopsie|tekst):", raw, re.I):
        return raw
    raw = re.sub(r"^/+", "", raw)
    raw = re.sub(r"^(data/)+", "", raw, flags=re.I)
    parts = [part for part in raw.split("/") if part]
    if not parts:
        return path.strip()
    obj = parts[-1]
    folder = "/".join(parts[:-1]).lower()
    if "personen" in folder:
        form = "persoon"
    elif "instellingen" in folder:
        form = "instelling"
    else:
        form = ""
    return f"{form}:{obj}" if form else f"ref:{obj}"


def to_plain(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = HTML_BR.sub("\n", text)
    text = HTML_P.sub("\n\n", text)
    text = HTML_TAG.sub("", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = wiki_to_markdown(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_empty(value) -> bool:
    if value is None:
        return True
    if value is False:
        return False
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value
    if isinstance(value, dict):
        return all(is_empty(item) for item in value.values())
    return False


def parse_formdef(root: ET.Element, project: str) -> dict | None:
    formkey = (root.findtext("formkey") or "").strip()
    if not formkey:
        return None
    fields = []
    wrapper = child(root, "form") or root
    for field in wrapper.findall("field"):
        key = (field.findtext("key") or "").strip()
        if not key:
            continue
        raw_type = (field.findtext("type") or "text").strip() or "text"
        repeater = (field.findtext("repeater") or "").strip().lower() == "true"
        if raw_type == "valuelist":
            ftype = "list" if repeater else "choice"
        elif raw_type == "property":
            ftype = "text"
        else:
            ftype = raw_type
        fields.append(
            {
                "key": key,
                "title": (field.findtext("title") or key).strip(),
                "type": ftype,
                "repeater": repeater,
                "subname": (field.findtext("subname") or "").strip() or None,
                "contents_key": (field.findtext("contents_key") or "").strip() or None,
                "widget": (field.findtext("widget_type") or "standard").strip() or "standard",
            }
        )
    return {
        "formkey": formkey,
        "formtitle": (root.findtext("formtitle") or formkey).strip(),
        "level": (root.findtext("level") or "main").strip() or "main",
        "namefield": (root.findtext("namefield") or "").strip() or None,
        "fields": fields,
        "project": project,
        "source_path": "",
    }


def parse_list(root: ET.Element) -> dict | None:
    key = (root.findtext("list_key") or root.findtext("key") or "").strip()
    if not key:
        return None
    items = []
    wrapper = child(root, "items") or root
    for item in wrapper.findall("item"):
        const = (item.findtext("item_key") or item.findtext("const") or "").strip()
        if not const:
            continue
        use = (item.findtext("use") or "use").strip().lower()
        items.append(
            {
                "const": const,
                "title": (item.findtext("item_value") or item.findtext("title") or const).strip(),
                "use": use not in ("false", "no", "0"),
            }
        )
    return {
        "key": key,
        "name": (root.findtext("name") or key).strip(),
        "sort_order": (root.findtext("sort_order") or "asdefined").strip(),
        "items": items,
    }


def project_from_lists_path(path: str) -> str:
    marker = "/ingforms/data/"
    if marker in path:
        rest = path.split(marker, 1)[1]
        return rest.split("/", 1)[0]
    return ""


def project_from_data_path(path: str) -> str:
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "content_repository":
        return parts[1]
    return parts[0] if parts else ""


class Catalog:
    def __init__(self):
        self.by_key: dict[str, list[dict]] = defaultdict(list)
        self.by_project: dict[str, dict[str, dict]] = defaultdict(dict)
        self.lists: dict[str, dict] = {}

    def add_formdef(self, defn: dict) -> None:
        self.by_key[defn["formkey"]].append(defn)
        if defn.get("project"):
            self.by_project[norm_name(defn["project"])][defn["formkey"]] = defn

    def resolve(self, formkey: str, project: str, data_path: str = "") -> dict | None:
        found = self.by_key.get(formkey)
        if not found:
            return None
        if len(found) == 1:
            return found[0]
        hay = norm_name(f"{project} {data_path}")
        skip = {
            "ingformslists",
            "ingforms",
            "data",
            "formdef",
            "contentrepository",
            "xml",
        }

        def score(defn: dict) -> int:
            points = 0
            if defn.get("project") and norm_name(defn["project"]) == norm_name(project):
                points += 50
            for part in (defn.get("source_path") or "").replace("\\", "/").split("/"):
                token = norm_name(part.replace("formdef_", ""))
                if not token or token in skip:
                    continue
                if token in hay:
                    points += min(len(token), 24)
            return points

        return max(found, key=score)

    def load_zip(self, zf: zipfile.ZipFile) -> None:
        for name in zf.namelist():
            if "/.svn/" in name or not name.endswith(".xml"):
                continue
            if "ingformslists" not in name:
                continue
            try:
                raw = zf.read(name)
            except KeyError:
                continue
            if b"<formdef" not in raw[:400] and b"<ingformslist" not in raw[:400]:
                continue
            try:
                root = ET.parse(io.BytesIO(raw)).getroot()
            except ET.ParseError:
                continue
            tag = local(root.tag)
            project = project_from_lists_path(name)
            if tag == "formdef":
                defn = parse_formdef(root, project)
                if defn:
                    defn["source_path"] = name
                    self.add_formdef(defn)
            elif tag == "ingformslist":
                lst = parse_list(root)
                if lst:
                    self.lists[lst["key"]] = lst


def convert_value(
    el: ET.Element | None,
    field: dict,
    catalog: Catalog,
    project: str,
    data_path: str = "",
):
    if el is None:
        return None
    ftype = field.get("type") or "text"
    if ftype in ("list", "choice"):
        sub = field.get("subname")
        nodes = children_named(el, sub) if sub else list(el)
        values = [leaf_text(node) for node in nodes]
        values = [item for item in values if item]
        if ftype == "choice":
            return values[0] if values else ""
        return values
    if ftype == "bool":
        raw = leaf_text(el).lower()
        return raw in ("true", "yes", "1")
    if ftype == "form":
        nested = catalog.resolve(field.get("contents_key") or "", project, data_path)
        sub = field.get("subname")
        if field.get("repeater"):
            nodes = children_named(el, sub) if sub else list(el)
            items = [
                convert_nested(node, nested, catalog, project, data_path)
                for node in nodes
            ]
            return [item for item in items if not is_empty(item)]
        return convert_nested(el, nested, catalog, project, data_path)
    return to_plain(leaf_text(el))


def convert_nested(
    el: ET.Element,
    nested: dict | None,
    catalog: Catalog,
    project: str,
    data_path: str = "",
):
    if nested and nested.get("fields"):
        keys = {field["key"] for field in nested["fields"]}
        if any(local(child_el.tag) in keys for child_el in list(el)):
            out = {}
            for field in nested["fields"]:
                value = convert_value(
                    child(el, field["key"]), field, catalog, project, data_path
                )
                if not is_empty(value):
                    if field["key"] == "relation" and isinstance(value, str):
                        value = relation_ref(value)
                    out[field["key"]] = value
            return out
        if len(nested["fields"]) == 1 and not list(el):
            key = nested["fields"][0]["key"]
            text = to_plain(leaf_text(el))
            if key == "relation":
                text = relation_ref(text)
            return {key: text} if text else {}
        if len(nested["fields"]) == 1:
            key = nested["fields"][0]["key"]
            text = to_plain(leaf_text(el))
            if key == "relation":
                text = relation_ref(text)
            return {key: text} if text else {}
    text = to_plain(leaf_text(el))
    return text if text else {}


def extra_islands(root: ET.Element, known: set[str]) -> dict:
    extra = {}
    for el in list(root):
        key = local(el.tag)
        if key in known or key in extra:
            continue
        if list(el):
            values = [to_plain(leaf_text(child_el)) for child_el in list(el)]
            values = [item for item in values if item]
            if values:
                extra[key] = values if len(values) > 1 else values[0]
            continue
        text = to_plain(leaf_text(el))
        if text:
            extra[key] = text
    return extra


def convert_document(
    root: ET.Element,
    catalog: Catalog,
    project: str,
    obj_name: str,
    data_path: str = "",
) -> dict | None:
    formkey = local(root.tag)
    if formkey in SKIP_ROOTS:
        return None
    defn = catalog.resolve(formkey, project, data_path)
    doc: dict = {"form": formkey, "text": "", "obj_name": obj_name}
    known = {"form", "text", "obj_name"}
    if defn:
        known.update(field["key"] for field in defn["fields"])
        for field in defn["fields"]:
            value = convert_value(
                child(root, field["key"]), field, catalog, project, data_path
            )
            if is_empty(value):
                continue
            if field["key"] == "text":
                doc["text"] = value if isinstance(value, str) else str(value)
                continue
            doc[field["key"]] = value
        if not doc["text"]:
            for key in TEXT_CANDIDATES:
                value = doc.get(key)
                if isinstance(value, str) and value.strip():
                    doc["text"] = value
                    break
    else:
        doc.update(extra_islands(root, known))
        if not doc["text"]:
            for key in TEXT_CANDIDATES:
                value = doc.get(key)
                if isinstance(value, str) and value.strip():
                    doc["text"] = value
                    break
        return doc
    doc.update(extra_islands(root, known))
    return doc


def iter_data_xml(zf: zipfile.ZipFile, project: str | None):
    want = norm_name(project) if project else None
    for name in zf.namelist():
        if "/.svn/" in name or not name.endswith(".xml"):
            continue
        if "ingformslists" in name:
            continue
        if not name.startswith("content_repository/"):
            continue
        proj = project_from_data_path(name)
        if want and norm_name(proj) != want:
            continue
        yield name, proj


def rewrite_value(value):
    if isinstance(value, str):
        if re.match(r"^/?(data/)+", value, re.I):
            return relation_ref(value)
        return wiki_to_markdown(value)
    if isinstance(value, list):
        if value and all(isinstance(item, str) and re.match(r"^/?(data/)+", item, re.I) for item in value):
            return [{"relation": relation_ref(item)} for item in value]
        return [rewrite_value(item) for item in value]
    if isinstance(value, dict):
        if "relation" in value and isinstance(value["relation"], str):
            out = {key: rewrite_value(item) for key, item in value.items() if key != "relation"}
            out["relation"] = relation_ref(value["relation"])
            return out
        return {key: rewrite_value(item) for key, item in value.items()}
    return value


def rewrite_document(doc: dict) -> dict:
    return {key: rewrite_value(value) for key, value in doc.items()}


def rewrite_folder(folder: Path, indent: int | None) -> int:
    written = 0
    for path in sorted(folder.rglob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("form"):
            continue
        path.write_text(
            json.dumps(rewrite_document(data), indent=indent, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written += 1
        if written % 2000 == 0:
            print(f"… {written} rewritten", file=sys.stderr)
    print(f"rewrote {written} documents in {folder}/", file=sys.stderr)
    return 0 if written else 1


def out_path(out_root: Path, zip_name: str) -> Path:
    rel = zip_name.split("content_repository/", 1)[-1]
    rel = os.path.splitext(rel)[0] + ".json"
    return out_root / rel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", help="Path to content_repository.zip")
    parser.add_argument("--out", type=Path, default=ROOT / "converted")
    parser.add_argument("--project", help="Only this project (e.g. emigratie)")
    parser.add_argument("--limit", type=int, default=0, help="Max documents (0 = all)")
    parser.add_argument("--indent", action="store_true")
    parser.add_argument("--catalog", action="store_true", help="Also write formdefs and lists")
    parser.add_argument(
        "--rewrite",
        type=Path,
        help="Rewrite wiki marks and /data/ relations in already converted JSON",
    )
    args = parser.parse_args(argv)

    if args.rewrite:
        return rewrite_folder(args.rewrite, 2 if args.indent else None)
    if not args.zip:
        raise SystemExit("--zip is required unless --rewrite is set")

    zf = zipfile.ZipFile(args.zip)
    catalog = Catalog()
    catalog.load_zip(zf)
    print(
        f"catalog: {sum(len(v) for v in catalog.by_key.values())} formdefs, "
        f"{len(catalog.lists)} lists",
        file=sys.stderr,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    if args.catalog:
        formdefs_out = {}
        for key, defs in catalog.by_key.items():
            formdefs_out[key] = defs[0] if len(defs) == 1 else defs
        (args.out / "_formdefs.json").write_text(
            json.dumps(formdefs_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (args.out / "_lists.json").write_text(
            json.dumps(catalog.lists, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    written = 0
    skipped = 0
    errors = 0
    unknown = 0
    forms = defaultdict(int)
    projects = defaultdict(int)
    indent = 2 if args.indent else None
    for zip_name, project in iter_data_xml(zf, args.project):
        if args.limit and written >= args.limit:
            break
        try:
            raw = zf.read(zip_name)
            root = ET.parse(io.BytesIO(raw)).getroot()
        except (ET.ParseError, KeyError, UnicodeDecodeError):
            errors += 1
            continue
        if local(root.tag) in SKIP_ROOTS:
            skipped += 1
            continue
        obj_name = os.path.splitext(os.path.basename(zip_name))[0]
        doc = convert_document(root, catalog, project, obj_name, zip_name)
        if not doc:
            skipped += 1
            continue
        if not catalog.resolve(doc["form"], project, zip_name):
            unknown += 1
        dest = out_path(args.out, zip_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(doc, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written += 1
        forms[doc["form"]] += 1
        projects[project] += 1
        if written % 2000 == 0:
            print(f"… {written} documents", file=sys.stderr)

    stats = {
        "written": written,
        "skipped": skipped,
        "parse_errors": errors,
        "unknown_form": unknown,
        "projects": dict(sorted(projects.items())),
        "forms": dict(sorted(forms.items(), key=lambda item: (-item[1], item[0]))),
    }
    (args.out / "_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {written} → {args.out}/  skipped {skipped}  "
        f"parse errors {errors}  unknown form {unknown}",
        file=sys.stderr,
    )
    return 0 if errors == 0 or written else 1


if __name__ == "__main__":
    sys.exit(main())
