# User guide

jsonforms is a transcription editor. You write (or paste) a text, then attach structured fields only where you need them. The result is a JSON file you can save, share, and load again.

The bundled example is Huygens ING Emigratie. The same editor works for any form you define.

## Open the editor

From the project folder:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

You can also open `index.html` directly. A local server is more reliable: the editor stores work in this browser, and some browsers treat each `file://` path as a different place.

## The screen

- **Left:** the transcription. This is the body of the document (`text`).
- **Right, Islands:** fields you have attached to this document.
- **Right, From the formdef:** fields you *could* attach but have not yet.
- **Top:** which form you are editing, load, save one file, and **Publish**.
- **Bottom:** status. **Show JSON** opens a live preview; you do not need it for ordinary work.

## Write a transcription

1. Choose a form in the menu (for the example: **Persoon**).
2. Paste or type in the large text area.
3. Leave it at that if you want. A document with only `text` is valid.

Work is stored in this browser a fraction of a second after you stop typing. Reload the page and it should still be there.

## Markdown (links and notes)

The transcription is Markdown, not HTML. The JSON still stores the source you typed. **Preview** on the left shows how it will read.

```markdown
Hij zat in het bestuur van de [Partij van de Arbeid](instelling:01PvdA).
Later werd hij commissaris.[^1]

[^1]: Benoemd november 1950; zie ook de dossierbeschrijving.
```

- `[label](persoon:01Haveman)` or `[label](ref:01SZ)` points at another record (`obj_name`).
- `https://…` links are ordinary web links.
- `[^1]` plus a `[^1]:` line at the bottom is an explanatory note.
- Old IngForms marks (`##01SZ# Ministerie##`) still preview as links.

Select a span for an island while **Edit** is showing, not Preview.

## Attach a field (an island)

The form lists possible fields. None of them are required.

1. Optionally select a span in the transcription.
2. Click the field name in **From the formdef**.
3. The island appears on the right. For a text field, the selected span is copied in as a starting value. You can edit it afterwards.

Remove an island with **remove**. That deletes the structured field from the document; the transcription is untouched.

## Field kinds you will see

| Kind | What you do |
|---|---|
| Short or long text | Type in the box |
| List | Tick one or more vocabulary items; filter if the list is long |
| Choice | Pick one value from a menu |
| Yes/no | Tick the box |
| Nested / repeating | **add item** for another block (a link, a field definition, an inventory line) |

You do not have to fill every nested box. Empty nested items are still stored if you added the island.

## Switch forms

The form menu lists **main** forms. Switching keeps a working copy of each form in this browser, so you can go back to Persoon after looking at Instelling.

There is currently **one working document per form**. Loading a JSON file for `persoon` replaces the persoon you had open, not a second record beside it.

## Save a file

**Save JSON** downloads the current document. That file is the copy that survives a new computer, a cleared browser, or a colleague’s machine.

A typical file looks like this:

```json
{
  "form": "persoon",
  "text": "Bastiaan Wouter Haveman werd in 1908 geboren …",
  "naam_archiefvormer": "Haveman, Bastiaan Wouter",
  "periode": "1908-1979"
}
```

`form` says which formdef applies. `text` is the transcription. Every other key is an island you attached. Fields you never used are simply absent. The precise JSON contract is [spec.md](spec.md).

**Publish** is different: it downloads a corpus (all working records plus the formdefs and vocabularies). Use that when the *set* of work is a version you would hand to an archive or a site. Details: [publishing.md](publishing.md).

## Load a file

**Load JSON** opens a file from disk. A single document becomes the current record. A published corpus (`kind: "formdef-corpus"`) replaces formdefs, lists, and working documents. If a document’s `form` is known, the editor switches to that form.

Load is how you continue work on another machine, or recover after clearing site data.

**Search** (in the header) is the published reader: free text, form, and clickable list/choice islands. It does not edit. See [publishing.md](publishing.md).

## If the browser crashes

Reopen the same address (`http://localhost:8000`, or the same `index.html` path). You should get the last stored version.

The last fraction of a second of typing may be missing. **Save JSON** when the text matters more than that.

## If work seems to have vanished

- You opened a different address (another port, or `file://` instead of localhost).
- The browser profile or “clear site data” wiped IndexedDB.
- You loaded a different JSON file, which replaced the working copy for that form.

Load the JSON you exported, if you have one.

## What this editor does not do yet

- Several records of the same form side by side (only one working persoon, one instelling, …).
- Accounts, sharing, or a server-side archive. Files and this browser are the two stores.
