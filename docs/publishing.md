# Publishing

Working copy, single-file save, and publish are three different acts.

| Act | What it is | Who it is for |
|---|---|---|
| Autosave | IndexedDB in this browser | the editor, so reload does not lose typing |
| **Save JSON** | one document, as you see it | backup, email, another machine |
| **Publish** | a corpus snapshot: formdefs + vocabularies + documents | a site, an archive, git |

A published corpus is the JSON other people (or a later static site) should read. It is not the working database.

## What gets published

**Publish** downloads a file like `corpus-2026-08-17.json`:

```json
{
  "kind": "formdef-corpus",
  "published": "2026-08-17T16:06:00.000Z",
  "formdefs": { "persoon": { "formkey": "persoon", "fields": [ … ] } },
  "lists": { "emigratie_land_herkomst": { "key": "…", "items": [ … ] } },
  "documents": [
    {
      "form": "persoon",
      "text": "…",
      "naam_archiefvormer": "Haveman, Bastiaan Wouter"
    }
  ]
}
```

- **formdefs** are the compiled catalogs (keys, types, nested forms), not the formdef *documents* with your editorial notes.
- **lists** are the vocabularies needed to interpret `list` / `choice` islands.
- **documents** are the current working records, one per form, minus the open formdef editor document.

Unused catalog fields stay out of each document, same as in the editor. Unknown extra islands stay in.

There is still only one working document per form. Publish therefore emits at most one `persoon`, one `instelling`, and so on. Several records of the same type need several corpora, or a later record-id model.

## In the editor

1. Finish the transcription and islands you want in the snapshot.
2. If you changed a formdef, leave it or save it first so migration has run.
3. Click **Publish**.
4. Keep that file. It is the release.

**Load JSON** on a corpus file replaces local formdefs, lists, and working documents with that snapshot. Use that to continue from a published pack, or to install someone else’s corpus in your browser.

**Save JSON** remains the way to export *this* record only.

## On disk

Unpack a corpus into catalogs and document files (does not overwrite `samples/` by default):

```bash
python3 scripts/unpack_corpus.py corpus-2026-08-17.json
```

Writes `formdefs/*.json`, `published/*.json` (one file per `form`), and `lists.json` if you pass `--lists`.

```bash
python3 scripts/unpack_corpus.py corpus-2026-08-17.json \
  --formdefs formdefs --documents published --lists lists.json
```

Commit `formdefs/` and `published/` (and lists, if you replaced them) when the snapshot is the version you mean to keep. Rebuild `bootstrap.js` if this checkout should seed new browsers with that catalog:

```bash
python3 scripts/build_bootstrap.py
```

`bootstrap.js` still seeds *first run* only. Browsers that already have IndexedDB keep their working copy until they load a corpus or clear site data.

## What publish is not

- Not a server, CMS, or public URL. The file is the publication.
- Not SVN/XML. IngForms wrote XML into a repository; this writes JSON you can put anywhere.
- Not a guarantee that nested formdefs inside documents were migrated. Top-level keys only; see [poweruser.md](poweruser.md).
- Not a substitute for **Save JSON** while you are still drafting one record.

## Suggested flow

1. Edit in the browser (working copy).
2. **Save JSON** when a single document should travel or be backed up.
3. **Publish** when the set of forms + records is a version you would hand to a site or an archive.
4. Unpack or commit the corpus if the project’s source of truth is git, not a browser profile.
