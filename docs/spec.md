# jsonforms specification

This is the interchange contract: what a document, a formdef, a vocabulary, and a published corpus *are*. Editorial use is in [user.md](user.md). How to edit catalogs is in [poweruser.md](poweruser.md). How the browser implements this is in [developer.md](developer.md).

Machine-readable shapes: [schema/jsonforms.schema.json](schema/jsonforms.schema.json) (`$defs.document`, `formdefCatalog`, `formdefDocument`, `list`, `corpus`, `bootstrap`, `searchData`).

The formats are not versioned yet. There is no `spec` field on documents. A corpus is identified by `kind: "formdef-corpus"`. Treat unknown properties as forward-compatible: keep them unless a migrator is explicitly dropping keys.

## 1. Encoding

Interchange is JSON as in RFC 8259, UTF-8, without a required BOM.

Writers in this project pretty-print with two-space indent, do not escape non-ASCII, and end the file with a newline. Readers MUST accept compact JSON and any legal whitespace.

Keys and string values are Unicode. There is no XML in the interchange format.

## 2. Identifiers

| Kind | Used as | Convention |
|---|---|---|
| **formkey** | document `form`; catalog `formkey` | XML local name / IngForms `formkey`. Recommended: `^[a-z][a-z0-9_]*$` |
| **field key** | JSON property on a document or nested object | same |
| **list key** | vocabulary id; field `contents_key` for `list` / `choice` | same, often prefixed (`emigratie_land_herkomst`) |

The editor does not validate the recommended pattern. Converted XML may use whatever the source root tag was.

Field keys are a **flat property namespace** on the document. Two main formdefs that both define `titel` share one JSON key and one search facet. Nested formdefs use the same rule inside their object, not on the parent.

**Reserved document keys** (not islands, not palette fields):

- `form` — formkey of the catalog that applies
- `text` — transcription body

If a catalog field also uses the key `text` (Emigratie `autopsie` does), that field *is* the body. It is not a separate island.

`obj_name` is not reserved. The XML converter sets it to the source file stem. The editor may store it as an ordinary island. Elasticsearch bulk ids prefer `obj_name`, then `id`, then `{form}-{index}`.

## 3. Document

A document is one JSON object.

```json
{
  "form": "persoon",
  "text": "Bastiaan Wouter Haveman werd in 1908 geboren …",
  "naam_archiefvormer": "Haveman, Bastiaan Wouter",
  "periode": "1908-1979"
}
```

| Property | Required | Type | Meaning |
|---|---|---|---|
| `form` | yes | string, non-empty | formkey |
| `text` | yes | string | transcription, CommonMark subset ([§3.1](#31-markdown-in-text)); may be `""` |
| *any other* | no | see [§5](#5-field-types-and-json-values) | island |

**Transcription first.** `text` is the document. Islands are optional structured fields attached to that body. A file with only `form` and `text` is valid.

### 3.1 Markdown in `text`

`text` is a string, not HTML. Inline structure is a **CommonMark subset**, stored as source:

| You write | Meaning |
|---|---|
| `*italic*` or `_italic_` | emphasis |
| `**bold**` | strong |
| `` `code` `` | inline code (escaped; not executed) |
| `[PvdA](instelling:01PvdA)` | internal record link (`formkey:obj_name`) |
| `[DANS](ref:01DANS)` | internal link by `obj_name` only |
| `[site](https://example.org)` | external URL (`http`/`https`/`mailto` only) |
| `Haveman[^1]` and `[^1]: …` on its own line | explanatory note (footnote) |
| blank line | paragraph |
| `- item` | unordered list |
| `## heading` | heading (one line) |

Raw HTML is not interpreted. `<` is shown as text. `javascript:` links are dropped.

IngForms leftovers still render: `##01SZ# Ministerie van Sociale Zaken##` and `#01PvdA#` become the same kind of internal link. Prefer Markdown in new text.

Person references belong in the transcription (`[label](persoon:01Haveman)`), not as HTML. Structured `*_link` islands remain for explicit relation lists.

The editor edits the source; **Preview** and `search.html` render it. Search still indexes the source string.

**Open catalog.** Unused formdef fields MUST be omitted, not stored as `null` or `""`. Unknown keys (not in the current formdef) MUST be preserved on load/save. The catalog is a menu of fields you *may* attach, not a closed schema.

**Attached but empty.** If the user attaches an island and clears it, the key may remain (`""`, `[]`, `false`, or `{}`). That is different from never attaching it. The XML converter omits empty values.

**One record per `form` in the editor.** IndexedDB and Publish key working documents by `form`. Several personen in one corpus is a later model; converted files on disk already have many records per formkey.

**No required record id.** Disk conversions use `obj_name` as a conventional handle. The editor does not mint ids.

Document `form` should match a compiled catalog. Readers SHOULD still accept the file if the catalog is missing: unknown keys remain islands.

## 4. Formdef catalog

A catalog describes islands a document of that `formkey` may have. It is **not** a document (`form` / `text` are absent). Files under `formdefs/*.json` are catalogs. `formdefs/index.json` is a human listing only; runtime loaders skip it.

```json
{
  "formkey": "persoon",
  "formtitle": "Persoon",
  "level": "main",
  "namefield": "naam_archiefvormer",
  "fields": [
    {
      "key": "naam_archiefvormer",
      "title": "Naam archiefvormer",
      "type": "text",
      "repeater": false,
      "subname": null,
      "contents_key": null,
      "widget": "standard"
    }
  ]
}
```

| Property | Required | Type | Meaning |
|---|---|---|---|
| `formkey` | yes | string | id; documents of this form set `form` to this |
| `formtitle` | no | string | menu label; default `formkey` |
| `level` | no | `"main"` \| `"secundair"` | menu vs nested-only. Default `"main"`. Spelling is IngForms’s `secundair`. |
| `namefield` | no | string or `null` | field key used as the human name in search |
| `fields` | yes | array | field specs; may be empty |
| `project` | no | string | XML converter provenance; unused by the editor |
| `source_path` | no | string | XML converter provenance; unused by the editor |

The form menu lists catalogs with `level === "main"`. `formdef` is listed first. Nested catalogs (`secundair`) are reached only through a `type: "form"` field’s `contents_key`.

### Field spec

| Property | Required | Type | Meaning |
|---|---|---|---|
| `key` | yes | string | JSON property. Specs with empty `key` are dropped at compile. |
| `title` | no | string | UI label; default `key` |
| `type` | no | see [§5](#5-field-types-and-json-values) | default `"text"` |
| `repeater` | no | boolean | value is an array. Default `false`. |
| `contents_key` | no | string or `null` | list key (`list` / `choice`) or nested formkey (`form`) |
| `subname` | no | string or `null` | IngForms XML child name; unused by the editor |
| `widget` | no | string | stored, currently ignored except the default `"standard"` |

Compile (document → catalog) trims strings, treats a one-element array `level` / `type` as a scalar, and sets `repeater` only when the value is boolean `true`.

The builtin catalogs `formdef` and `formdef_field` describe the formdef editor itself. They are ordinary catalogs.

## 5. Field types and JSON values

Allowed `type` values: `text`, `list`, `choice`, `form`, `bool`.

| type | repeater | JSON value |
|---|---|---|
| `text` | false | string |
| `text` | true | array of strings (rare; prefer `list`) |
| `list` | ignored; treated as multi | array of vocabulary `const` strings |
| `choice` | false | one `const` string, or `""` |
| `bool` | false | `true` or `false` |
| `form` | false | object whose keys are the nested catalog’s field keys |
| `form` | true | array of those objects |

`contents_key` MUST be a list key for `list` / `choice`, or a formkey for `form`. A missing target means an empty widget / empty nested object, not a hard error.

**List / choice store `const`, not `title`.** Display labels live only on the vocabulary.

**Nested objects are sparse or dense.** The converter omits empty nested keys. The editor, when attaching a nested island, may fill every nested key with an empty value. Both are valid. Nested objects MAY contain unknown keys; they are kept.

**Relations** (Emigratie `*_link` fields) are `type: "form"`, `repeater: true`, `contents_key: "relation_form"`:

```json
"functies_link": [
  { "relation": "/data/nederland/instellingen/overige actoren particulier/01Nederlandse Stichting tot Steun van het ICEM" }
]
```

The `relation` string is an IngForms path. The editor does not resolve it. Inline mentions in `text` use Markdown links instead ([§3.1](#31-markdown-in-text)).

**Inventory lines** (Emigratie autopsie) are the same pattern with `contents_key: "autopsie_inventaris"`:

```json
"archief": [
  {
    "inventarisomschrijving": "…",
    "anker": "inv-12",
    "omschrijving": "…"
  }
]
```

IngForms wiki-style marks inside strings (`##id# label##`) are rendered as internal links. Prefer Markdown `[label](ref:id)` in new text.

## 6. Formdef document

A formdef is also a document, so the same editor can change the catalog.

```json
{
  "form": "formdef",
  "text": "Definition of Persoon. …",
  "formkey": "persoon",
  "formtitle": "Persoon",
  "level": "main",
  "namefield": "naam_archiefvormer",
  "fields": [ { "key": "periode", "title": "Leefjaren", "type": "text", "repeater": false } ]
}
```

| Shape | How you get it | What it is |
|---|---|---|
| Catalog | `formdefs/*.json`, corpus `formdefs`, bootstrap | no `form` / `text` |
| Formdef document | **Save JSON** while editing a formdef | `form: "formdef"` plus catalog islands |

**Load JSON** accepts both:

1. If `kind === "formdef-corpus"` and `documents` is an array → corpus (replaces session).
2. Else if `formkey` is set, `fields` is an array, and `form` is not `"formdef"` → catalog; it is published and opened via a fresh formdef document.
3. Else → ordinary document (`loadDocument`).

Compiling a formdef document to a catalog does **not** keep `text`. Turning a catalog back into a document synthesizes a new notes sentence. Editorial notes on a formdef survive only in the formdef *document* file, not in `formdefs/*.json`.

A formdef document is excluded from **Publish** `documents` (`form !== "formdef"`). Its compiled catalog is included in corpus `formdefs`.

## 7. Vocabularies (lists)

Lists are a JSON object keyed by list key.

```json
{
  "emigratie_land_herkomst": {
    "key": "emigratie_land_herkomst",
    "name": "Emigratie: land van herkomst archiefvormer",
    "sort_order": "asdefined",
    "items": [
      { "const": "nederland", "title": "Nederland", "use": true }
    ]
  }
}
```

| Property | Required | Meaning |
|---|---|---|
| `key` | yes | same as the object key |
| `name` | no | label |
| `sort_order` | no | IngForms leftover; `"asdefined"` means keep `items` order |
| `items` | yes | array of items |

| Item | Required | Meaning |
|---|---|---|
| `const` | yes | stored on the document |
| `title` | no | shown in UI; default `const` |
| `use` | no | `false` hides the item without deleting it. Default treated as visible (`use !== false`). |

On disk this project splits:

- `lists.json` — project vocabularies
- `lists-meta.json` — `formdef_level`, `formdef_field_type`

Bootstrap and the editor merge them into one map. A corpus stores the merged map under `lists`.

There is no list editor in the UI.

## 8. Corpus pack

A published snapshot of catalogs, vocabularies, and documents. **Publish** writes this file. **Load JSON** on it replaces the session (no merge).

```json
{
  "kind": "formdef-corpus",
  "published": "2026-08-17T16:06:00.000Z",
  "formdefs": {
    "persoon": { "formkey": "persoon", "formtitle": "Persoon", "level": "main", "fields": [ ] }
  },
  "lists": {
    "emigratie_land_herkomst": { "key": "emigratie_land_herkomst", "items": [ ] }
  },
  "documents": [
    { "form": "persoon", "text": "…", "naam_archiefvormer": "Haveman, Bastiaan Wouter" }
  ]
}
```

| Property | Required | Meaning |
|---|---|---|
| `kind` | yes | MUST be `"formdef-corpus"` |
| `published` | no | ISO-8601 timestamp; default now on write |
| `formdefs` | no | map of formkey → catalog |
| `lists` | no | map of list key → list |
| `documents` | yes | array of documents (may be empty) |

A pack is recognized iff `kind` is `"formdef-corpus"` and `documents` is an array.

Corpus `formdefs` are compiled catalogs, not formdef documents. Corpus `documents` omit `form: "formdef"`.

The current editor emits **at most one document per `form`**. Many files of the same form (the XML conversion) are valid as a corpus `documents` array; the editor will keep only the last of each `form` if that pack is loaded.

Unpack to git:

```bash
python3 scripts/unpack_corpus.py corpus-YYYY-MM-DD.json
```

Writes `formdefs/{formkey}.json` and `published/{form}.json`.

## 9. Bootstrap and search pack

Not interchange for archives; they are inlined browser payloads.

**`bootstrap.js`** (first-run seed and `file://`):

```js
window.BOOTSTRAP = {
  formdefs: { /* formkey → catalog */ },
  lists: { /* list key → list */ },
  draft: { /* one document, typically samples/persoon-draft.json */ }
};
```

Built by `scripts/build_bootstrap.py`. IndexedDB is seeded only when `meta.seeded` is missing.

**`search-data.js`** (static reader):

```js
window.SEARCH_DATA = {
  formdefs: { /* catalogs */ },
  lists: { /* lists */ },
  documents: [ /* documents */ ]
};
```

Built by `scripts/build_search.py` from `formdefs/`, lists, `published/`, and `samples/`. `search.html` also accepts **Load corpus**. It does not read IndexedDB.

## 10. Search mapping

Search roles are derived from formdefs. There is no separate search schema file.

| Source | Role |
|---|---|
| document `text` | analyzed full text (plus every string island in the static reader) |
| document `form` | exact filter |
| catalog `namefield` | name search |
| every `list` / `choice` field on **main** formdefs (`formkey !== "formdef"`) | keyword facet; first formdef that defines the key wins |

Optional Elasticsearch mapping (`mapping.js` / `scripts/corpus_to_es.py`):

| JSON | ES |
|---|---|
| `form` | `keyword` |
| `text` | `text` |
| `namefield` keys | `text` + `raw` keyword subfield |
| `list` / `choice` | `keyword` |
| `bool` | `boolean` |
| `form` repeater | `nested` |
| `form` single | `object` |
| other | `text` |

This project does not run Elasticsearch. `es/` output is optional.

## 11. Migration

When a catalog changes, documents may still have old keys. The plan is computed from the previous published catalog vs the new one (`diffFormdefs`):

- Same index in `fields`, old key gone, new key new, neither key present on the other side → **rename**.
- Extra `--rename old=new` (disk migrator) is applied the same way.
- Type or `repeater` change → **coerce** (`migrate.js` `coerceValue`).
- Key removed from the formdef → **drop**, unless `--keep-removed`.
- Unknown extra islands → **keep**, unless `--drop-unknown`.

Coercion (summary):

| Target | Rule |
|---|---|
| `bool` | `true` / `"true"` / `"yes"`; arrays: any element true |
| `choice` | first array element, else `String(value)`, else `""` |
| `list` or any repeater | wrap a scalar in an array; `null`/`""` → `[]` |
| `form` repeater | array of objects; object → `[object]` |
| `form` single | first array element or object or `{}` |
| `text` | arrays joined with newline; objects `JSON.stringify`; else `String` |

Migration walks **top-level keys only**. Nested `form` values are not rewritten. Changing `relation_form` or `autopsie_inventaris` does not update existing nested objects.

The editor migrates open documents when leaving the formdef editor or saving a formdef. Disk: `scripts/update_documents.py`.

## 12. XML conversion

IngForms XML is not the interchange format. `scripts/convert_ingforms_xml.py` writes jsonforms documents.

Each data XML file becomes:

```json
{ "form": "<root tag>", "text": "…", "obj_name": "<file stem>", "…": "islands" }
```

Rules:

- Catalogs and lists are read from `ingformslists` in the zip. Shared formkeys (e.g. `vereniging`, `persoon`) are resolved by scoring the formdef path against the data path (`formdef_sport` vs `formdef_armenzorg`).
- Field types follow the formdef (`valuelist` → `list` or `choice`; `property` → `text`).
- `list` / `choice` values are `subname` children, as `const` strings.
- Repeating `form` children become arrays of nested objects; relation wrappers become `{ "relation": "…" }`.
- HTML stored as escaped markup is unescaped and stripped to plaintext (`<br>` / `</p>` → newlines, tags removed, `&nbsp;` → space).
- `text` is taken from the `text` field if present; otherwise from the first non-empty of `tekst`, `transcriptie`, `biografie`, `regest`, `omschrijving`, `inhoud`, `contents`, `samenvatting`, `organisatie`, `taak`, `doelstelling`.
- If no formdef matches the root tag, non-empty child elements become islands of the same names.
- Empty values are omitted. Output is `converted/{project}/{relative path}.json` (gitignored).

Four Emigratie examples: `scripts/convert_emigratie_xml.py` → `samples/*-full.json`.

## 13. Runtime store (informative)

Not an interchange format. The editor’s working copy is IndexedDB database `formdef`, version 1:

| store | key | value |
|---|---|---|
| `docs` | `form` | document |
| `formdefs` | `formkey` | catalog |
| `meta` | `"lists"` / `"lastForm"` / `"seeded"` | vocabularies, last formkey, boolean |

Autosave is origin-scoped. It is not a corpus. **Save JSON** and **Publish** are the files other tools should read.

## 14. Conformance

A **document writer** MUST emit `form` and `text`, MUST omit unused catalog fields, and MUST NOT use `form` or `text` as island names.

A **document reader** MUST accept extra properties, MUST treat a missing island as unattached, and SHOULD look up `form` in a catalog when one is available.

A **catalog writer** MUST emit `formkey` and `fields`, and SHOULD emit `type` / `repeater` / `contents_key` as in [§4](#4-formdef-catalog) and [§5](#5-field-types-and-json-values).

A **corpus writer** MUST set `kind` to `"formdef-corpus"` and MUST give `documents` as an array. Catalogs in `formdefs` MUST be catalogs, not formdef documents.

A **corpus reader** MUST replace (not merge) catalogs, lists, and documents when loading a pack into an editor session.

## 15. Current limits

These are part of the present contract, not accidents:

- Editor and Publish: one working document per `form`.
- Nested migration is not defined.
- Vocabularies are not editable in the UI.
- `widget` and `subname` are stored for round-trip and ignored by the UI.
- No merge if two tabs share an origin; last write wins.
