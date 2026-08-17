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

No build. Python 3 is only used for optional scripts. The bundled example is Huygens ING **Emigratie**.

## Run

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000>. Or open `index.html` directly (`file://` can make local storage flaky).

## Docs

| Who | Guide |
|---|---|
| Editing transcriptions | [docs/user.md](docs/user.md) |
| Formdefs, vocabularies, migration, files | [docs/poweruser.md](docs/poweruser.md) |
| Publishing a corpus | [docs/publishing.md](docs/publishing.md) |
| Architecture and scripts | [docs/developer.md](docs/developer.md) |
