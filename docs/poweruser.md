# Power user guide

This is for people who define forms, keep vocabularies, and move documents between the editor and disk. Editorial day-to-day use is in [user.md](user.md). The interchange contract (document, formdef, list, corpus) is [spec.md](spec.md).

## Document shape

Every document is JSON:

| key | meaning |
|---|---|
| `form` | formdef id (`formkey`) |
| `text` | transcription body; always present |
| *any other key* | an island; stored only if attached |

Unknown keys are kept. That is deliberate: you can structure a few fields now and more later, and you can keep data the current formdef does not mention.

`form` and `text` are not islands. They are never in the palette.

## Formdefs

A formdef is the catalog of islands a document *may* have. It is not a required schema. Empty catalog fields stay out of the file.

The catalog is itself a document (`form`: `formdef`), edited in the same app.

### Fields of a formdef

| key | meaning |
|---|---|
| `formkey` | stable id; becomes `form` on documents and the JSON property namespace |
| `formtitle` | label in the form menu |
| `level` | `main` appears in the menu; `secundair` is nested only |
| `namefield` | which field is a human name (hint; not enforced) |
| `fields` | repeating list of field specs |

### Fields of a field spec

| key | meaning |
|---|---|
| `key` | JSON property on the document |
| `title` | label in the editor |
| `type` | `text`, `list`, `choice`, `form`, `bool` |
| `repeater` | value is an array |
| `contents_key` | vocabulary id (`list` / `choice`) or nested `formkey` (`form`) |
| `subname` | XML-era child name; unused by the editor, kept for round-trip |
| `widget` | unused besides `standard`; kept for round-trip |

### Edit an existing form

**Edit formdef** opens the current form as a formdef document. Attach **Form key**, **Title**, **Fields**, and so on from the palette if they are missing.

**add item** under Fields creates another field spec. Set `key` and `title` at least. As soon as `formkey` is set, the form is published into the menu (for `level` `main`).

**New formdef** starts an empty definition. Give it a `formkey` before you expect it in the menu.

Typing in the formdef editor **does not** rewrite open documents on every keystroke. Migration runs when you **leave** the formdef (switch form) or **Save JSON**. That avoids scrambling a record while you are mid-rename.

### Two JSON shapes for formdefs

**Save JSON** while editing a formdef downloads the *document* (with `form`, `text`, notes, and field islands):

```json
{
  "form": "formdef",
  "text": "Definition of Persoon. …",
  "formkey": "persoon",
  "formtitle": "Persoon",
  "level": "main",
  "fields": [ … ]
}
```

The files under `formdefs/` are the *compiled catalog* (no `form` / `text`):

```json
{
  "formkey": "persoon",
  "formtitle": "Persoon",
  "level": "main",
  "namefield": "naam_archiefvormer",
  "fields": [ … ]
}
```

**Load JSON** accepts both. A catalog object (`formkey` + `fields`, and not `form: "formdef"`) is converted into a formdef document and published.

## Types and JSON values

| type | repeater | JSON |
|---|---|---|
| `text` | no | string |
| `text` | yes | array of strings (unusual; lists are the usual multi-value) |
| `list` | (treat as multi) | array of vocabulary `const` strings |
| `choice` | no | one `const` string, or `""` |
| `bool` | no | `true` / `false` |
| `form` | no | object whose keys are the nested formdef’s fields |
| `form` | yes | array of those objects |

`contents_key` must match a list in `lists.json` / `lists-meta.json`, or a `formkey` of another formdef.

## Vocabularies

Lists live in `lists.json` (project vocabularies) and `lists-meta.json` (formdef level and field type). Shape:

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

`const` is stored on the document. `title` is shown. `use: false` hides an item without deleting it.

There is no list editor in the UI. Edit the JSON, then rebuild bootstrap (see below) or load a session that already has the lists in IndexedDB from an earlier seed.

## Local store versus files

| Store | Role |
|---|---|
| IndexedDB | working copy: documents, formdefs, last-open form |
| **Save JSON** | one document, interchange and backup |
| **Publish** | corpus snapshot: formdefs + lists + documents |

IndexedDB is tied to the **origin** (`http://localhost:8000` is not `http://localhost:8001`, and not a `file://` path). First visit seeds from `bootstrap.js`. Later visits restore the database, not a fresh bootstrap, so editing `formdefs/` on disk does not overwrite a user’s local formdefs until they load those files.

One document is stored per `form` key. Stash + current snapshot are written together, about 400ms after the last change, and again when the tab is hidden.

**Save JSON** exports the current record. **Publish** exports the working set as a corpus. The publishing flow (load a corpus, unpack to git) is in [publishing.md](publishing.md).

## Migrate documents after a formdef change

When a field is renamed, retyped, or removed, old JSON still has the old keys.

In the editor, leaving the formdef (or saving it) rewrites **open** documents for that `formkey`:

- Same slot in `fields`, old key gone, new key new → treated as a **rename**.
- Type or `repeater` change → value is **coerced** (list ↔ string, bool, nested object, …).
- Key removed from the formdef → dropped from the document.
- Unknown extra islands → kept.

That migrator is **top-level keys only**. Nested objects (relations, inventaris lines) are not walked.

For files on disk, dry-run first:

```bash
python3 scripts/update_documents.py \
  --from old/persoon.json --to formdefs/persoon.json \
  --rename periode=leefjaren \
  samples/
```

Write in place:

```bash
python3 scripts/update_documents.py \
  --from old/persoon.json --to formdefs/persoon.json \
  --write samples/
```

| flag | effect |
|---|---|
| `--rename old=new` | extra rename (repeatable) |
| `--write` | overwrite files; default is print-only |
| `--keep-removed` | leave keys that disappeared from the formdef |
| `--drop-unknown` | drop islands the formdef does not mention |

## Rebuild the inlined catalog

The editor does not fetch `formdefs/` at runtime. `bootstrap.js` is a packed copy for `file://` and first-run seed.

After editing `formdefs/*.json`, `lists.json`, `lists-meta.json`, or `samples/persoon-draft.json`:

```bash
python3 scripts/build_bootstrap.py
```

Reload. Existing IndexedDB is **not** re-seeded. To pick up disk formdefs in a browser that already ran the editor: **Load JSON** on the catalog files, or clear this origin’s site data (that also drops working documents).

## Optional XML import

IngForms XML lives in `content_repository.zip` (not in this repo). Convert to jsonforms documents (`form`, `text`, islands):

```bash
python3 scripts/convert_ingforms_xml.py --zip /path/to/content_repository.zip
python3 scripts/convert_ingforms_xml.py --zip … --project emigratie --indent
python3 scripts/convert_emigratie_xml.py --zip …   # four samples/ → *-full.json
```

Output of the full converter is `converted/` (gitignored). Formdefs in the zip are used when present; otherwise non-empty XML children become islands. `text` is filled from a transcription-like field when one exists.
