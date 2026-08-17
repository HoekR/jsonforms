# jsonforms

A browser-only editor for transcription-first JSON documents.

A document is a large `text` body. Structured fields are optional **islands**. A **formdef** is the catalog of islands you *may* attach; unused fields stay out of the file. Formdefs are edited in the same app — a formdef is itself a document.

```json
{
  "form": "persoon",
  "text": "Bastiaan Wouter Haveman werd in 1908 geboren …",
  "naam_archiefvormer": "Haveman, Bastiaan Wouter",
  "periode": "1908-1979"
}
```

No build, no server required for the editor itself. Python 3 is only used for optional scripts.

The bundled example is Huygens ING **Emigratie** (`persoon`, `instelling`, `autopsie`, `tekst`).

## Run

A tiny static server is the reliable way (IndexedDB is origin-scoped; `file://` can be flaky):

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000>.

Or open `index.html` directly.

- Paste a transcription. Select a span, then add an island from the palette.
- **Edit formdef** opens the current form as a formdef document. Add a field by adding an item to the `fields` island. As soon as it has a `formkey`, it appears in the form menu.
- **New formdef** starts an empty definition.
- Work is kept in this browser (IndexedDB) and restored on reload.
- **Save JSON** serializes the current document to a file. **Load JSON** brings a file back in.

## Layout

| path | role |
|---|---|
| `index.html` | editor shell |
| `editor.js` / `editor.css` | UI |
| `db.js` | IndexedDB working copy |
| `migrate.js` | rewrite documents after a formdef change |
| `bootstrap.js` | inlined formdefs, vocabularies, and draft (for `file://`) |
| `formdefs/` | formdef catalog; source for bootstrap |
| `lists.json` / `lists-meta.json` | vocabularies |
| `samples/` | example documents |
| `scripts/` | rebuild bootstrap, migrate files, optional XML import |

## Field types

| type | JSON value |
|---|---|
| `text` | string |
| `list` | array of vocabulary keys |
| `choice` | one vocabulary key |
| `bool` | true/false |
| `form` | nested object, or array if `repeater` |

`contents_key` is a list id or the `formkey` of a nested formdef.

## Rebuild the inlined catalog

After editing files under `formdefs/` or the lists:

```bash
python3 scripts/build_bootstrap.py
```

## Updating documents after a formdef change

Renaming a field, changing its type, or removing it leaves old JSON behind. The editor rewrites open records when you leave the formdef (or save it): same slot + old key gone counts as a rename; values are coerced to the new type.

For files on disk:

```bash
python3 scripts/update_documents.py \
  --from old/persoon.json --to formdefs/persoon.json \
  --rename periode=leefjaren \
  samples/

python3 scripts/update_documents.py \
  --from old/persoon.json --to formdefs/persoon.json --write samples/
```

The first command is a dry-run. Unknown extra islands are kept. Keys removed from the formdef are dropped unless you pass `--keep-removed`.

## Optional: import IngForms XML

If you have the old `content_repository.zip`, write a few sample records into `samples/`:

```bash
python3 scripts/convert_emigratie_xml.py --zip /path/to/content_repository.zip
```
