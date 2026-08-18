const searchState = {
  formdefs: {},
  lists: {},
  documents: [],
  query: "",
  name: "",
  form: "",
  facets: {},
  selected: null,
};

function listTitle(contentsKey, value) {
  const list = searchState.lists[contentsKey];
  if (!list) return value;
  const item = (list.items || []).find((entry) => entry.const === value);
  return item ? item.title || item.const : value;
}

function fieldValues(doc, key) {
  const value = doc[key];
  if (value == null || value === "") return [];
  if (Array.isArray(value)) return value.filter((item) => item != null && item !== "");
  return [value];
}

function stripHtml(value) {
  return String(value).replace(/<[^>]+>/g, " ");
}

function walkStrings(value, into) {
  if (value == null) return;
  if (typeof value === "string") {
    into.push(stripHtml(value));
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) walkStrings(item, into);
    return;
  }
  if (typeof value === "object") {
    for (const item of Object.values(value)) walkStrings(item, into);
  }
}

function haystack(doc) {
  const parts = [];
  walkStrings(doc, parts);
  return parts.join(" ").toLowerCase();
}

function docName(doc) {
  const schema = searchSchema(searchState.formdefs);
  const key = schema.namefield[doc.form];
  if (key && doc[key]) return stripHtml(String(doc[key]));
  return doc.titel || doc.formtitle || doc.obj_name || doc.form || "—";
}

function termMatches(hay, term) {
  if (term.includes("*")) {
    const escaped = term.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*");
    return new RegExp(escaped, "i").test(hay);
  }
  return hay.includes(term);
}

function matches(doc, options) {
  const skip = options && options.skipFacet;
  if (searchState.form && doc.form !== searchState.form) return false;
  if (searchState.name) {
    if (!docName(doc).toLowerCase().includes(searchState.name.toLowerCase())) return false;
  }
  for (const [key, selected] of Object.entries(searchState.facets)) {
    if (key === skip || !selected.size) continue;
    const values = new Set(fieldValues(doc, key).map(String));
    let hit = false;
    for (const item of selected) {
      if (values.has(item)) {
        hit = true;
        break;
      }
    }
    if (!hit) return false;
  }
  const raw = searchState.query.trim().toLowerCase();
  if (!raw) return true;
  const hay = haystack(doc);
  for (const term of raw.split(/\s+/).filter(Boolean)) {
    if (!termMatches(hay, term)) return false;
  }
  return true;
}

function filtered(options) {
  return searchState.documents.filter((doc) => matches(doc, options));
}

function facetCounts(facet) {
  const counts = {};
  for (const doc of filtered({ skipFacet: facet.key })) {
    for (const value of fieldValues(doc, facet.key)) {
      const key = String(value);
      counts[key] = (counts[key] || 0) + 1;
    }
  }
  return counts;
}

function toggleFacet(key, value) {
  if (!searchState.facets[key]) searchState.facets[key] = new Set();
  const set = searchState.facets[key];
  if (set.has(value)) set.delete(value);
  else set.add(value);
  renderSearch();
}

function clearFilters() {
  searchState.query = "";
  searchState.name = "";
  searchState.form = "";
  searchState.facets = {};
  const q = document.getElementById("q");
  const name = document.getElementById("name-filter");
  if (q) q.value = "";
  if (name) name.value = "";
  renderSearch();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function highlight(text) {
  const raw = searchState.query.trim();
  const safe = escapeHtml(stripHtml(text || ""));
  if (!raw) return safe;
  const terms = raw.split(/\s+/).filter(Boolean);
  let out = safe;
  for (const term of terms) {
    const source = term.replace(/\*/g, "");
    if (!source) continue;
    const pattern = new RegExp(source.replace(/[.+?^${}()|[\]\\]/g, "\\$&"), "gi");
    out = out.replace(pattern, (match) => `<mark>${match}</mark>`);
  }
  return out;
}

function snippet(doc) {
  const text = markdownPlain(doc.text || "");
  return text.slice(0, 280) + (text.length > 280 ? "…" : "");
}

function findByRef(form, id) {
  if (!id) return null;
  const exact = searchState.documents.find(
    (doc) => doc.obj_name === id && (!form || doc.form === form)
  );
  if (exact) return exact;
  return searchState.documents.find((doc) => doc.obj_name === id) || null;
}

function bindMarkdownLinks(root) {
  for (const link of root.querySelectorAll("a.md-ref")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const doc = findByRef(link.dataset.form, link.dataset.ref);
      if (!doc) return;
      searchState.selected = doc;
      renderSearch();
    });
  }
}

function loadPack(pack) {
  searchState.formdefs = pack.formdefs || {};
  searchState.lists = pack.lists || {};
  searchState.documents = (pack.documents || []).filter(
    (doc) => doc && doc.form && doc.form !== "formdef"
  );
  searchState.selected = null;
  searchState.facets = {};
}

function renderForms() {
  const root = document.getElementById("form-filter");
  const forms = [...new Set(searchState.documents.map((doc) => doc.form))];
  forms.sort();
  const buttons = ['<button type="button" data-form="" class="chip">All</button>'];
  for (const form of forms) {
    const def = searchState.formdefs[form];
    const label = def?.formtitle || form;
    buttons.push(`<button type="button" data-form="${escapeHtml(form)}" class="chip">${escapeHtml(label)}</button>`);
  }
  root.innerHTML = buttons.join("");
  for (const btn of root.querySelectorAll("button")) {
    btn.classList.toggle("on", (btn.dataset.form || "") === searchState.form);
    btn.addEventListener("click", () => {
      searchState.form = btn.dataset.form || "";
      renderSearch();
    });
  }
}

function renderFacets() {
  const root = document.getElementById("facets");
  root.innerHTML = "";
  const schema = searchSchema(searchState.formdefs);
  for (const facet of schema.facets) {
    const counts = facetCounts(facet);
    const keys = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
    if (!keys.length) continue;
    const section = document.createElement("section");
    const title = document.createElement("h3");
    title.textContent = facet.title;
    section.appendChild(title);
    const selected = searchState.facets[facet.key] || new Set();
    for (const key of keys) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip";
      if (selected.has(key)) btn.classList.add("on");
      btn.textContent = `${listTitle(facet.contents_key, key)} (${counts[key]})`;
      btn.addEventListener("click", () => toggleFacet(facet.key, key));
      section.appendChild(btn);
    }
    root.appendChild(section);
  }
}

function renderResults() {
  const root = document.getElementById("results");
  const hits = filtered();
  hits.sort((a, b) => docName(a).localeCompare(docName(b), "nl"));
  document.getElementById("hit-count").textContent = `${hits.length} record${hits.length === 1 ? "" : "s"}`;
  root.innerHTML = "";
  if (!hits.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Nothing matches. Clear filters or load a published corpus.";
    root.appendChild(empty);
    return;
  }
  hits.forEach((doc) => {
    const article = document.createElement("article");
    article.className = "hit";
    if (searchState.selected === doc) article.classList.add("on");
    const kicker = document.createElement("p");
    kicker.className = "kicker";
    const def = searchState.formdefs[doc.form];
    kicker.textContent = def?.formtitle || doc.form;
    const title = document.createElement("h3");
    title.innerHTML = highlight(docName(doc));
    const body = document.createElement("p");
    body.innerHTML = highlight(snippet(doc));
    article.append(kicker, title, body);
    article.addEventListener("click", () => {
      searchState.selected = doc;
      renderSearch();
    });
    root.appendChild(article);
  });
}

function renderDetail() {
  const root = document.getElementById("detail");
  const doc = searchState.selected;
  if (!doc) {
    root.innerHTML = `<p class="hint">Select a record.</p>`;
    return;
  }
  const schema = searchSchema(searchState.formdefs);
  const def = searchState.formdefs[doc.form];
  const facets = new Map((schema.facets || []).map((facet) => [facet.key, facet]));
  let html = `<p class="kicker">${escapeHtml(def?.formtitle || doc.form)}</p>`;
  html += `<h2>${highlight(docName(doc))}</h2>`;
  html += `<div class="body markdown-body">${markdownToHtml(doc.text || "")}</div>`;
  const fields = def?.fields || [];
  for (const field of fields) {
    if (!(field.key in doc) || field.key === "text") continue;
    const values = fieldValues(doc, field.key);
    if (!values.length) continue;
    html += `<section class="island-read"><h3>${escapeHtml(field.title || field.key)}</h3>`;
    const facet = facets.get(field.key);
    if (facet) {
      html += `<div class="chips">`;
      for (const value of values) {
        const label = listTitle(facet.contents_key, String(value));
        html += `<button type="button" class="chip" data-facet="${escapeHtml(facet.key)}" data-value="${escapeHtml(String(value))}">${escapeHtml(label)}</button>`;
      }
      html += `</div>`;
    } else if (typeof doc[field.key] === "string") {
      html += `<div class="markdown-body">${markdownToHtml(doc[field.key])}</div>`;
    } else {
      html += `<pre>${escapeHtml(JSON.stringify(doc[field.key], null, 2))}</pre>`;
    }
    html += `</section>`;
  }
  root.innerHTML = html;
  bindMarkdownLinks(root);
  for (const btn of root.querySelectorAll("button.chip")) {
    btn.addEventListener("click", () => toggleFacet(btn.dataset.facet, btn.dataset.value));
  }
}

function renderSearch() {
  renderForms();
  renderFacets();
  renderResults();
  renderDetail();
}

function bindSearch() {
  document.getElementById("q").addEventListener("input", (event) => {
    searchState.query = event.target.value;
    renderSearch();
  });
  document.getElementById("name-filter").addEventListener("input", (event) => {
    searchState.name = event.target.value;
    renderSearch();
  });
  document.getElementById("clear-filters").addEventListener("click", clearFilters);
  document.getElementById("load-corpus").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const data = JSON.parse(await file.text());
    if (!isCorpus(data)) {
      window.alert("That file is not a published corpus (kind formdef-corpus).");
      event.target.value = "";
      return;
    }
    loadPack(data);
    renderSearch();
    event.target.value = "";
  });
}

function bootSearch() {
  const data = window.SEARCH_DATA || {};
  loadPack(data);
  bindSearch();
  renderSearch();
}

bootSearch();
