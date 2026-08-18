/** Small Markdown subset for transcriptions. No raw HTML. */

function markdownEscape(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function markdownAttr(value) {
  return markdownEscape(value).replace(/'/g, "&#39;");
}

function markdownIngforms(source) {
  let text = String(source || "");
  text = text.replace(/##([^#\n]+)#([^#\n]+)##/g, (_, id, label) => {
    return `[${label.trim()}](ref:${id.trim()})`;
  });
  text = text.replace(/(^|[^#])#([A-Za-z0-9][^#\n]{0,80}?)#/g, (match, pre, id) => {
    if (id.startsWith(" ")) return match;
    return `${pre}[${id}](ref:${id})`;
  });
  return text;
}

function markdownParseHref(raw) {
  const href = String(raw || "").trim();
  if (!href || /^(javascript|data|vbscript):/i.test(href)) return { kind: "unsafe" };
  if (/^https?:\/\//i.test(href) || /^mailto:/i.test(href)) return { kind: "url", href };
  if (href.startsWith("#")) return { kind: "hash", href };
  let rest = href.replace(/^ref:/i, "");
  const colon = rest.indexOf(":");
  if (colon > 0) {
    const form = rest.slice(0, colon);
    const id = rest.slice(colon + 1);
    if (/^[a-z][a-z0-9_]*$/i.test(form) && id) return { kind: "doc", form, id };
  }
  return { kind: "doc", form: "", id: rest };
}

function markdownLink(labelHtml, href) {
  const parsed = markdownParseHref(href);
  if (parsed.kind === "unsafe") return labelHtml;
  if (parsed.kind === "url") {
    return `<a href="${markdownAttr(parsed.href)}" target="_blank" rel="noopener noreferrer">${labelHtml}</a>`;
  }
  if (parsed.kind === "hash") {
    return `<a href="${markdownAttr(parsed.href)}">${labelHtml}</a>`;
  }
  return (
    `<a href="#doc" class="md-ref" data-form="${markdownAttr(parsed.form)}" data-ref="${markdownAttr(parsed.id)}">` +
    `${labelHtml}</a>`
  );
}

function markdownInline(source, notes) {
  const slots = [];
  const hold = (html) => {
    const token = `\u0000${slots.length}\u0000`;
    slots.push(html);
    return token;
  };
  let text = String(source || "");
  text = text.replace(/`([^`]+)`/g, (_, code) => hold(`<code>${markdownEscape(code)}</code>`));
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    return hold(markdownLink(markdownEscape(label), href));
  });
  text = text.replace(/\[\^([^\]]+)\]/g, (_, id) => {
    if (!notes[id]) return `[^${id}]`;
    const slug = markdownSlug(id);
    return hold(
      `<sup class="md-fn" id="fnref-${slug}"><a href="#fn-${slug}">${markdownEscape(id)}</a></sup>`
    );
  });
  text = markdownEscape(text);
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  text = text.replace(/(^|[^a-zA-Z0-9_])_([^_]+)_/g, "$1<em>$2</em>");
  return text.replace(/\u0000(\d+)\u0000/g, (_, i) => slots[Number(i)]);
}

function markdownSlug(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]+/g, "-");
}

function markdownFootnotes(source) {
  const notes = {};
  const body = String(source || "").replace(/^\[\^([^\]]+)\]:\s*(.*)$/gm, (_, id, text) => {
    notes[id] = text;
    return "";
  });
  return { body, notes };
}

function markdownBlock(block, notes) {
  const trimmed = block.replace(/[ \t]+$/gm, "").trim();
  if (!trimmed) return "";
  const lines = trimmed.split("\n");
  if (lines.length && lines.every((line) => /^[-*] /.test(line))) {
    const items = lines
      .map((line) => `<li>${markdownInline(line.replace(/^[-*] /, ""), notes)}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }
  const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
  if (heading && !trimmed.includes("\n")) {
    const level = Math.min(heading[1].length + 2, 5);
    return `<h${level}>${markdownInline(heading[2], notes)}</h${level}>`;
  }
  const html = lines.map((line) => markdownInline(line, notes)).join("<br>\n");
  return `<p>${html}</p>`;
}

function markdownToHtml(source) {
  const prepared = markdownIngforms(source || "");
  const { body, notes } = markdownFootnotes(prepared);
  const blocks = body.replace(/^\s+|\s+$/g, "").split(/\n{2,}/);
  const html = blocks.map((block) => markdownBlock(block, notes)).join("\n");
  const ids = Object.keys(notes);
  if (!ids.length) return html;
  const items = ids
    .map((id) => {
      const slug = markdownSlug(id);
      return (
        `<li id="fn-${slug}">${markdownInline(notes[id], notes)} ` +
        `<a href="#fnref-${slug}" class="md-fn-back">↩</a></li>`
      );
    })
    .join("");
  return `${html}\n<aside class="md-footnotes"><ol>${items}</ol></aside>`;
}

function markdownPlain(source) {
  return markdownIngforms(source || "")
    .replace(/^\[\^([^\]]+)\]:\s*.*$/gm, "")
    .replace(/\[\^([^\]]+)\]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[*_`#]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
