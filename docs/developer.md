# Developer guide

Browser-only editor. No bundler, no framework, no backend. Python 3 is used only for packing bootstrap and for file migrators.

Editorial use: [user.md](user.md). Formdefs, lists, and migration: [poweruser.md](poweruser.md). Corpus snapshot: [publishing.md](publishing.md). Interchange formats: [spec.md](spec.md).

## Layout

| path | role |
|---|---|
| `index.html` | shell; script order `bootstrap.js` → `migrate.js` → `db.js` → `publish.js` → `markdown.js` → `editor.js` |
| `editor.css` | layout and type |
| `editor.js` | document model, formdef compile/publish, UI |
| `markdown.js` | CommonMark subset for `text` (preview + search) |
| `db.js` | IndexedDB open / seed / load / save |
| `publish.js` | `formdef-corpus` pack (`isCorpus`, `buildCorpus`) |
| `migrate.js` | `diffFormdefs`, `coerceValue`, `migrateDocument` |
| `mapping.js` | formdef → facets / Elasticsearch mapping |
| `search.html` / `search.js` / `search.css` | static gids-style reader |
| `search-data.js` | inlined documents for `search.html` |
| `bootstrap.js` | generated `window.BOOTSTRAP` |
| `formdefs/*.json` | compiled catalogs; `index.json` is a listing, skipped by the packer |
| `lists.json` | project vocabularies |
| `lists-meta.json` | `formdef_level`, `formdef_field_type` |
| `samples/` | example documents |
| `docs/spec.md` | interchange specification |
| `docs/schema/jsonforms.schema.json` | JSON Schema for those shapes |
| `scripts/build_bootstrap.py` | pack formdefs + lists + draft → `bootstrap.js` |
| `scripts/update_documents.py` | same migration rules for files on disk |
| `scripts/convert_ingforms_xml.py` | IngForms XML zip → jsonforms documents in `converted/` (gitignored) |
| `scripts/convert_emigratie_xml.py` | four Emigratie samples → `samples/*-full.json` |
| `scripts/unpack_corpus.py` | corpus JSON → `formdefs/` + `published/` |
| `scripts/build_search.py` | pack samples/published → `search-data.js` |
| `scripts/corpus_to_es.py` | corpus or samples → `es/mapping.json` + `es/bulk.ndjson` |

Fonts load from Google if the machine is online; the editor runs without them.

## Boot

1. `bind()` attaches DOM listeners.
2. `openDb()` opens IndexedDB `formdef` v1.
3. If `meta.seeded` is missing, `dbSeed` writes bootstrap formdefs, lists, and `samples/persoon-draft.json`.
4. `applyLoaded` restores formdefs, lists, all docs (stash), and `lastForm`.
5. On IDB failure, `applyBootstrap` keeps everything in memory. Status: `Memory only — IndexedDB unavailable`.

Later visits **do not** re-seed. Disk changes to `formdefs/` are invisible until bootstrap is rebuilt *and* the origin’s DB is empty, or the user loads catalog JSON.

## Runtime state

```js
state = {
  db,          // IDB database or null
  formdefs,    // { [formkey]: compiled catalog }
  published,   // last stable catalog per formkey (migration baseline)
  lists,       // { [listKey]: { key, name, items } }
  formkey,     // current form menu selection
  stash,       // { [form]: document }  — one slot per form
  doc,         // current document
  jsonOpen,    // JSON preview
}
```

`snapshot()` is `{ form, text, ...islands }`. `form` and `text` are meta (`META`); they are not palette fields.

## Persistence

Database name `formdef`, version 1:

| store | key | value |
|---|---|---|
| `docs` | `form` | document snapshot |
| `formdefs` | `formkey` | compiled catalog |
| `meta` | `"lists"` / `"lastForm"` / `"seeded"` | vocabularies, last formkey, boolean |

`persistSoon` debounce is 400ms. `persistNow` writes all stash docs plus the current snapshot, all formdefs, and `lastForm`. Lists are written on seed only.

`visibilitychange` → hidden calls `persistNow`. A hard crash can lose the debounce window and any in-flight transaction; IDB transactions are atomic, so you get the previous complete snapshot.

## Formdefs in the same app

`compileFormdef(doc)` turns a `form: "formdef"` document into a catalog. `formdefToDoc(def)` is the inverse (notes in `text` are a fresh sentence, not preserved through compile).

`publishFormdef(doc, { migrate })`:

- Always updates `state.formdefs[formkey]` once `formkey` is non-empty.
- **Without** `migrate` (every keystroke in the formdef editor): does not rewrite documents; does not update `published` if that key already existed. Mid-edit renames must not scramble open records.
- **With** `migrate` (leaving the formdef via `setForm`, or Save JSON, or loading a formdef file): `diffFormdefs(published, compiled)` then `migrateOpenDocuments` for stash + current doc whose `form` matches.

`diffFormdefs` rename heuristic: same index in `fields`, old key absent from the new set, new key absent from the old set.

`migrateDocument` is top-level keys only. Nested `form` values are not walked. Keep that in mind if `relation_form` or `autopsie_inventaris` fields change.

Load JSON special case: `{ formkey, fields }` without `form: "formdef"` is treated as a compiled catalog, published, and opened via `formdefToDoc`.

The form menu lists catalogs with `level === "main"`. `formdef` is sorted first.

## Rendering

`renderControl` is shared by top-level islands and nested form fields. Nested repeaters call `render()` after add/remove so the tree is rebuilt; ordinary island `input` events only call `afterChange` (persist + header + optional JSON).

`SHORT_TEXT` is a hard-coded set of keys that get a short textarea. There is no widget switch in the UI yet (`widget` is stored and ignored beyond `standard`).

List widgets read `state.lists[contents_key].items` and skip `use === false`.

## JSON preview

The dock does not stringify on every keystroke. `state.jsonOpen` must be true. Save JSON always uses `snapshot()`, not the preview.

## Publishing

`buildCorpus` in `publish.js` is the on-disk / download shape. `kind` must be `formdef-corpus`.

**Publish** (`downloadCorpus`) migrates if the formdef editor is open, then downloads compiled `formdefs`, `lists`, and stash documents with `form !== "formdef"`. Filename `corpus-YYYY-MM-DD.json`.

**Load JSON** calls `isCorpus` first. `loadCorpus` replaces `state.formdefs` / `published` / `lists` / `stash` from the pack (it does not merge).

`scripts/unpack_corpus.py` writes the same split to disk for git. `search.html` reads a corpus or `search-data.js`; it does not use IndexedDB. `mapping.js` / `scripts/corpus_to_es.py` derive keyword facets and an ES mapping from formdef types.

A published corpus is not the IndexedDB working copy. Autosave keeps drafts; publish is an explicit snapshot.

## Bootstrap packer

`scripts/build_bootstrap.py` concatenates every `formdefs/*.json` except `index.json`, merges `lists.json` + `lists-meta.json`, reads `samples/persoon-draft.json`, and writes:

```js
window.BOOTSTRAP = { formdefs, lists, draft };
```

Commit `bootstrap.js` so `file://` and first-run seed work without running Python.

## Known limits (intentional or unfinished)

- One document per `form` key; no record id, no list of personen.
- Nested formdef migration is not implemented.
- Vocabularies are not editable in the UI.
- No conflict/merge if two tabs share the origin; last write wins.
- `file://` IndexedDB is origin-per-path and flaky; prefer `python3 -m http.server`.
- Emigratie bulk types from the XML corpus (`verbalen`, …) are not in the bundled editor formdefs.
- Many zip projects have no formdef; the converter then copies non-empty XML children as islands.

## Conventions

- No build step for the editor. Keep scripts classic (no modules) so `file://` script tags work.
- Do not live-serialize large transcriptions; persist structured clones in IDB; serialize on export.
- Prefer keeping unknown document keys over enforcing the catalog as a closed schema.
