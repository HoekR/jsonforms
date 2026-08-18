const META = new Set(["form", "text"]);
const SHORT_TEXT = new Set([
  "naam_archiefvormer",
  "periode",
  "periode_van_bestaan",
  "titel",
  "anker",
  "ankernaam",
  "obj_name",
  "datum_laatste_verandering",
  "formkey",
  "formtitle",
  "namefield",
  "key",
  "contents_key",
  "subname",
  "widget",
]);

const state = {
  db: null,
  formdefs: {},
  published: {},
  lists: {},
  formkey: "persoon",
  stash: {},
  doc: { form: "persoon", text: "" },
  jsonOpen: false,
  previewOpen: false,
};

let persistTimer = 0;

function setStatus(message) {
  const el = document.getElementById("status");
  if (el) el.textContent = message;
}

function workspaceDocs() {
  const docs = { ...state.stash, [state.doc.form]: snapshot() };
  return Object.values(docs).filter((doc) => doc && doc.form);
}

function persistSoon() {
  clearTimeout(persistTimer);
  persistTimer = window.setTimeout(() => {
    persistNow().catch((error) => {
      console.warn(error);
      setStatus("Could not save locally");
    });
  }, 400);
}

async function persistNow() {
  if (!state.db) {
    setStatus("Memory only");
    return;
  }
  await dbSaveWorkspace(state.db, {
    docs: workspaceDocs(),
    formdefs: Object.values(state.formdefs),
    lastForm: state.formkey,
  });
  setStatus("Stored in this browser");
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function formdef() {
  return state.formdefs[state.formkey];
}

function fieldMap() {
  const map = {};
  for (const field of formdef()?.fields || []) map[field.key] = field;
  return map;
}

function islands() {
  return Object.keys(state.doc).filter((key) => !META.has(key));
}

function emptyValue(field) {
  if (field.type === "bool") return false;
  if (field.type === "choice") return "";
  if (field.type === "list" || field.repeater) return [];
  if (field.type === "form") return field.repeater ? [] : nestedEmpty(field);
  return "";
}

function nestedEmpty(field) {
  const nested = state.formdefs[field.contents_key];
  if (!nested) return {};
  const item = {};
  for (const sub of nested.fields) item[sub.key] = emptyValue(sub);
  return item;
}

function listItems(key) {
  const list = state.lists[key];
  if (!list) return [];
  return list.items.filter((item) => item.use !== false);
}

function download(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function selectedText() {
  const area = document.getElementById("text");
  if (!area) return "";
  return area.value.slice(area.selectionStart, area.selectionEnd).trim();
}

function snapshot() {
  const out = { form: state.doc.form, text: state.doc.text };
  for (const key of islands()) out[key] = state.doc[key];
  return out;
}

function addIsland(key, seed) {
  const field = fieldMap()[key];
  if (!field || key in state.doc) return;
  let value = emptyValue(field);
  if (typeof value === "string" && seed) value = seed;
  state.doc[key] = value;
  afterChange();
  render();
}

function removeIsland(key) {
  delete state.doc[key];
  afterChange();
  render();
}

function setForm(formkey) {
  state.stash[state.formkey] = snapshot();
  if (state.doc.form === "formdef") publishFormdef(state.doc, { migrate: true });
  state.formkey = formkey;
  state.doc = state.stash[formkey] || { form: formkey, text: "" };
  state.doc.form = formkey;
  persistSoon();
  render();
}

function publishedDocuments() {
  return workspaceDocs().filter((doc) => doc.form && doc.form !== "formdef");
}

function downloadCorpus() {
  if (state.doc.form === "formdef") publishFormdef(state.doc, { migrate: true });
  const pack = buildCorpus({
    formdefs: state.formdefs,
    lists: state.lists,
    documents: publishedDocuments(),
  });
  persistNow().catch(() => {});
  download(`corpus-${pack.published.slice(0, 10)}.json`, pack);
  setStatus("Published corpus downloaded");
}

function loadCorpus(data) {
  const pack = buildCorpus(data);
  const formdefs = {};
  for (const [key, def] of Object.entries(pack.formdefs || {})) {
    const formkey = def && (def.formkey || key);
    if (!formkey || !def) continue;
    formdefs[formkey] = def;
  }
  if (Object.keys(formdefs).length) {
    state.formdefs = formdefs;
    state.published = clone(formdefs);
  }
  if (pack.lists && Object.keys(pack.lists).length) state.lists = pack.lists;
  state.stash = {};
  for (const doc of pack.documents) {
    if (doc && doc.form && doc.form !== "formdef") state.stash[doc.form] = doc;
  }
  const preferred =
    (state.stash[state.formkey] && state.formkey) ||
    pack.documents.find((doc) => doc && doc.form && doc.form !== "formdef")?.form;
  const formkey =
    (preferred && state.formdefs[preferred] && preferred) ||
    Object.keys(state.formdefs).find((key) => state.formdefs[key]?.level === "main") ||
    Object.keys(state.formdefs)[0] ||
    "persoon";
  state.formkey = formkey;
  state.doc = state.stash[formkey] || { form: formkey, text: "" };
  persistSoon();
  render();
  setStatus("Loaded published corpus");
}

function loadDocument(doc) {
  if (!doc || typeof doc !== "object") return;
  const next = { form: doc.form || state.formkey, text: doc.text || "", ...doc };
  if (next.form && state.formdefs[next.form]) state.formkey = next.form;
  state.doc = next;
  state.stash[next.form] = snapshot();
  if (next.form === "formdef") publishFormdef(next, { migrate: true });
  persistSoon();
  render();
}

function scalar(value) {
  if (Array.isArray(value)) return value[0] || "";
  return value ?? "";
}

function compileFormdef(doc) {
  const formkey = (doc.formkey || "").trim();
  if (!formkey) return null;
  const fields = Array.isArray(doc.fields) ? doc.fields : [];
  return {
    formkey,
    formtitle: (doc.formtitle || formkey).trim(),
    level: scalar(doc.level) || "main",
    namefield: (doc.namefield || "").trim() || null,
    fields: fields
      .filter((field) => field && (field.key || "").trim())
      .map((field) => ({
        key: field.key.trim(),
        title: (field.title || field.key).trim(),
        type: scalar(field.type) || "text",
        repeater: field.repeater === true,
        subname: (field.subname || "").trim() || null,
        contents_key: (field.contents_key || "").trim() || null,
        widget: (field.widget || "standard").trim() || "standard",
      })),
  };
}

function formdefToDoc(def) {
  return {
    form: "formdef",
    text: `Definition of ${def.formtitle || def.formkey}. Add or change field islands; this form becomes usable as soon as it has a form key.`,
    formkey: def.formkey,
    formtitle: def.formtitle || def.formkey,
    level: def.level || "main",
    namefield: def.namefield || "",
    fields: (def.fields || []).map((field) => ({
      key: field.key,
      title: field.title,
      type: field.type || "text",
      repeater: !!field.repeater,
      subname: field.subname || "",
      contents_key: field.contents_key || "",
      widget: field.widget || "standard",
    })),
  };
}

function publishFormdef(doc, options) {
  const def = compileFormdef(doc);
  if (!def) return;
  const migrate = options && options.migrate;
  const previous = state.published[def.formkey];
  state.formdefs[def.formkey] = def;
  if (migrate && previous) {
    const plan = diffFormdefs(previous, def);
    if (!planIsEmpty(plan)) migrateOpenDocuments(plan);
  }
  if (migrate || !previous) state.published[def.formkey] = clone(def);
}

function migrateOpenDocuments(plan) {
  const apply = (doc) => migrateDocument(doc, plan).doc;
  for (const [key, doc] of Object.entries(state.stash)) {
    if (doc && doc.form === plan.formkey) state.stash[key] = apply(doc);
  }
  if (state.doc.form === plan.formkey) state.doc = apply(state.doc);
}

function afterChange() {
  if (state.doc.form === "formdef") publishFormdef(state.doc);
  persistSoon();
  if (state.jsonOpen) renderJson();
  renderHeader();
}

function editCurrentDefinition() {
  const def = formdef();
  if (!def) return;
  state.stash[state.formkey] = snapshot();
  state.formkey = "formdef";
  state.doc = formdefToDoc(def);
  state.stash.formdef = state.doc;
  persistSoon();
  render();
}

function newFormdef() {
  state.stash[state.formkey] = snapshot();
  state.formkey = "formdef";
  state.doc = {
    form: "formdef",
    text: "Describe the new form here. Attach form key, title, and fields as islands.",
  };
  state.stash.formdef = state.doc;
  persistSoon();
  render();
}

function renderHeader() {
  const select = document.getElementById("formkey");
  const current = state.formkey;
  const mains = Object.values(state.formdefs).filter((d) => d.level === "main");
  mains.sort((a, b) => {
    if (a.formkey === "formdef") return -1;
    if (b.formkey === "formdef") return 1;
    return (a.formtitle || a.formkey).localeCompare(b.formtitle || b.formkey);
  });
  select.innerHTML = "";
  for (const def of mains) {
    const opt = document.createElement("option");
    opt.value = def.formkey;
    opt.textContent = def.formtitle || def.formkey;
    if (def.formkey === current) opt.selected = true;
    select.appendChild(opt);
  }
}

function renderText() {
  const area = document.getElementById("text");
  const preview = document.getElementById("text-preview");
  const toggle = document.getElementById("toggle-preview");
  if (area.value !== (state.doc.text || "")) area.value = state.doc.text || "";
  if (!preview || !toggle) return;
  if (state.previewOpen) {
    preview.innerHTML = markdownToHtml(state.doc.text || "") || `<p class="hint">Nothing to preview.</p>`;
    preview.classList.remove("hidden");
    area.classList.add("hidden");
    toggle.textContent = "Edit";
  } else {
    preview.classList.add("hidden");
    area.classList.remove("hidden");
    toggle.textContent = "Preview";
  }
}

function onIslandValue(key, value) {
  state.doc[key] = value;
  afterChange();
}

function renderControl(field, value, onChange) {
  if (field.type === "list") return renderList(field, value, onChange);
  if (field.type === "choice") return renderChoice(field, value, onChange);
  if (field.type === "bool") return renderBool(value, onChange);
  if (field.type === "form" && field.repeater) return renderRepeatForm(field, value, onChange);
  if (field.type === "form") {
    return renderNested(field, value, onChange);
  }
  const area = document.createElement("textarea");
  area.className = SHORT_TEXT.has(field.key) ? "short" : "";
  area.value = value ?? "";
  area.addEventListener("input", () => onChange(area.value));
  return area;
}

function renderIsland(field, value) {
  const wrap = document.createElement("article");
  wrap.className = "island";
  wrap.dataset.key = field.key;

  const head = document.createElement("div");
  head.className = "island-head";
  const title = document.createElement("strong");
  title.textContent = field.title;
  const drop = document.createElement("button");
  drop.type = "button";
  drop.className = "quiet";
  drop.textContent = "remove";
  drop.addEventListener("click", () => removeIsland(field.key));
  head.append(title, drop);
  wrap.appendChild(head);
  wrap.appendChild(renderControl(field, value, (next) => onIslandValue(field.key, next)));
  return wrap;
}

function renderList(field, value, onChange) {
  const box = document.createElement("div");
  const selected = new Set(Array.isArray(value) ? value : []);
  const items = listItems(field.contents_key);
  const filter = document.createElement("input");
  filter.className = "filter";
  filter.placeholder = "filter…";
  const checks = document.createElement("div");
  checks.className = "checks";

  function paint(q = "") {
    checks.innerHTML = "";
    const query = q.toLowerCase();
    for (const item of items) {
      const hay = `${item.const} ${item.title}`.toLowerCase();
      if (query && !hay.includes(query)) continue;
      const lab = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selected.has(item.const);
      cb.addEventListener("change", () => {
        if (cb.checked) selected.add(item.const);
        else selected.delete(item.const);
        onChange([...selected]);
      });
      lab.append(cb, document.createTextNode(item.title || item.const));
      checks.appendChild(lab);
    }
  }
  filter.addEventListener("input", () => paint(filter.value));
  paint();
  box.append(filter, checks);
  if (!items.length) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = `No list loaded for ${field.contents_key || "—"}.`;
    box.appendChild(note);
  }
  return box;
}

function renderChoice(field, value, onChange) {
  const select = document.createElement("select");
  const current = scalar(value);
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "—";
  select.appendChild(blank);
  for (const item of listItems(field.contents_key)) {
    const opt = document.createElement("option");
    opt.value = item.const;
    opt.textContent = item.title;
    if (item.const === current) opt.selected = true;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function renderBool(value, onChange) {
  const lab = document.createElement("label");
  lab.className = "inline";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = value === true;
  cb.addEventListener("change", () => onChange(cb.checked));
  lab.append(cb, document.createTextNode("yes"));
  return lab;
}

function renderRepeatForm(field, value, onChange) {
  const box = document.createElement("div");
  const items = Array.isArray(value) ? value : [];
  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "repeat-item";
    const label = document.createElement("div");
    label.className = "hint";
    label.textContent = item.title || item.key || item.formkey || `#${index + 1}`;
    row.appendChild(label);
    row.appendChild(
      renderNested(field, item, (next) => {
        const copy = items.slice();
        copy[index] = next;
        onChange(copy);
      })
    );
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "quiet";
    rm.textContent = "remove item";
    rm.addEventListener("click", () => {
      const copy = items.slice();
      copy.splice(index, 1);
      onChange(copy);
      render();
    });
    row.appendChild(rm);
    box.appendChild(row);
  });
  const add = document.createElement("button");
  add.type = "button";
  add.textContent = "add item";
  add.addEventListener("click", () => {
    const seed = nestedEmpty(field);
    const selected = selectedText();
    if (selected && "key" in seed && !seed.key) seed.key = selected;
    if (selected && "title" in seed && !seed.title) seed.title = selected;
    onChange(items.concat([seed]));
    render();
  });
  box.appendChild(add);
  return box;
}

function renderNested(field, value, onChange) {
  const nested = state.formdefs[field.contents_key];
  const box = document.createElement("div");
  if (!nested) {
    box.textContent = `Unknown nested formdef: ${field.contents_key}`;
    return box;
  }
  const current = value && typeof value === "object" ? { ...value } : nestedEmpty(field);
  for (const sub of nested.fields) {
    const lab = document.createElement("div");
    lab.style.marginTop = "0.35rem";
    const name = document.createElement("div");
    name.className = "hint";
    name.textContent = sub.title;
    lab.appendChild(name);
    lab.appendChild(
      renderControl(sub, current[sub.key], (next) => {
        current[sub.key] = next;
        onChange({ ...current });
      })
    );
    box.appendChild(lab);
  }
  return box;
}

function renderIslands() {
  const root = document.getElementById("islands");
  root.innerHTML = "";
  const fields = fieldMap();
  const keys = islands().filter((key) => fields[key]);
  if (!keys.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Nothing structured yet. The transcription can stand on its own.";
    root.appendChild(empty);
    return;
  }
  for (const key of keys) {
    root.appendChild(renderIsland(fields[key], state.doc[key]));
  }
}

function renderPalette() {
  const root = document.getElementById("palette");
  root.innerHTML = "";
  const used = new Set(islands());
  for (const field of formdef()?.fields || []) {
    if (used.has(field.key)) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = field.title;
    btn.title = field.key;
    btn.addEventListener("click", () => addIsland(field.key, selectedText()));
    root.appendChild(btn);
  }
}

function renderJson() {
  const pre = document.getElementById("json");
  const btn = document.getElementById("toggle-json");
  const dock = document.querySelector(".json-dock");
  if (!pre) return;
  if (btn) btn.textContent = state.jsonOpen ? "Hide JSON" : "Show JSON";
  if (dock) dock.classList.toggle("open", state.jsonOpen);
  if (!state.jsonOpen) {
    pre.classList.add("hidden");
    pre.textContent = "";
    return;
  }
  pre.classList.remove("hidden");
  pre.textContent = JSON.stringify(snapshot(), null, 2);
}

function render() {
  renderHeader();
  renderText();
  renderIslands();
  renderPalette();
  renderJson();
}

function bind() {
  document.getElementById("text").addEventListener("input", (event) => {
    state.doc.text = event.target.value;
    afterChange();
  });
  document.getElementById("formkey").addEventListener("change", (event) => {
    setForm(event.target.value);
  });
  document.getElementById("edit-formdef").addEventListener("click", editCurrentDefinition);
  document.getElementById("new-formdef").addEventListener("click", newFormdef);
  document.getElementById("toggle-json").addEventListener("click", () => {
    state.jsonOpen = !state.jsonOpen;
    renderJson();
  });
  document.getElementById("toggle-preview").addEventListener("click", () => {
    state.previewOpen = !state.previewOpen;
    renderText();
  });
  document.getElementById("save-json").addEventListener("click", () => {
    if (state.doc.form === "formdef") publishFormdef(state.doc, { migrate: true });
    const data = snapshot();
    const name =
      data.form === "formdef"
        ? `${data.formkey || "formdef"}.formdef.json`
        : `${data.form || "document"}.json`;
    persistNow().catch(() => {});
    download(name, data);
  });
  document.getElementById("publish").addEventListener("click", downloadCorpus);
  document.getElementById("load-file").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const data = JSON.parse(await file.text());
    if (isCorpus(data)) loadCorpus(data);
    else if (data.formkey && Array.isArray(data.fields) && data.form !== "formdef") {
      state.formdefs[data.formkey] = data;
      loadDocument(formdefToDoc(data));
    } else {
      loadDocument(data);
    }
    event.target.value = "";
  });
}

function applyLoaded(loaded, bootstrap) {
  const formdefs = {};
  for (const def of loaded.formdefs || []) {
    if (def && def.formkey) formdefs[def.formkey] = def;
  }
  if (!Object.keys(formdefs).length) Object.assign(formdefs, bootstrap.formdefs || {});
  state.formdefs = formdefs;
  state.published = clone(formdefs);
  state.lists =
    loaded.lists && Object.keys(loaded.lists).length ? loaded.lists : bootstrap.lists || {};
  state.stash = {};
  for (const doc of loaded.docs || []) {
    if (doc && doc.form) state.stash[doc.form] = doc;
  }
  const last = loaded.lastForm || bootstrap.draft?.form || "persoon";
  state.formkey = formdefs[last] ? last : Object.keys(formdefs)[0] || "persoon";
  state.doc = state.stash[state.formkey] || { form: state.formkey, text: "" };
}

function applyBootstrap(bootstrap) {
  state.formdefs = bootstrap.formdefs || {};
  state.published = clone(state.formdefs);
  state.lists = bootstrap.lists || {};
  if (bootstrap.draft) {
    state.doc = bootstrap.draft;
    state.formkey = bootstrap.draft.form || "persoon";
    state.stash[state.formkey] = bootstrap.draft;
  }
}

async function boot() {
  bind();
  const bootstrap = window.BOOTSTRAP || {};
  try {
    state.db = await openDb();
    let loaded = await dbLoad(state.db);
    if (!loaded.seeded) {
      await dbSeed(state.db, bootstrap);
      loaded = await dbLoad(state.db);
    }
    applyLoaded(loaded, bootstrap);
    setStatus("Stored in this browser");
  } catch (error) {
    console.warn(error);
    applyBootstrap(bootstrap);
    setStatus("Memory only — IndexedDB unavailable");
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") persistNow().catch(() => {});
  });
  render();
}

boot();
