/** Diff formdefs and rewrite document islands after key/type changes. */

function fieldList(def) {
  return def && Array.isArray(def.fields) ? def.fields : [];
}

function diffFormdefs(oldDef, newDef, extraRenames) {
  const oldFields = fieldList(oldDef);
  const newFields = fieldList(newDef);
  const oldKeys = oldFields.map((field) => field.key);
  const newKeys = newFields.map((field) => field.key);
  const oldSet = new Set(oldKeys);
  const newSet = new Set(newKeys);
  const renames = { ...(extraRenames || {}) };

  const shared = Math.min(oldFields.length, newFields.length);
  for (let i = 0; i < shared; i++) {
    const from = oldFields[i].key;
    const to = newFields[i].key;
    if (from === to || newSet.has(from) || oldSet.has(to) || renames[from]) continue;
    renames[from] = to;
  }

  const removed = oldKeys.filter((key) => !newSet.has(key) && !renames[key]);
  const typeChanges = [];
  for (const next of newFields) {
    const previousKey =
      Object.keys(renames).find((key) => renames[key] === next.key) || next.key;
    const prev = oldFields.find((field) => field.key === previousKey);
    if (!prev) continue;
    if (prev.type !== next.type || !!prev.repeater !== !!next.repeater) {
      typeChanges.push({ key: next.key, from: prev, to: next });
    }
  }

  return {
    formkey: newDef.formkey,
    renames,
    removed,
    typeChanges,
    fields: newFields,
  };
}

function coerceValue(value, field) {
  if (value === undefined) return undefined;
  if (field.type === "bool") {
    if (typeof value === "boolean") return value;
    if (Array.isArray(value)) return value.some((item) => item === true || item === "true");
    return value === true || value === "true" || value === "yes";
  }
  if (field.type === "choice") {
    if (Array.isArray(value)) return value[0] || "";
    if (value == null) return "";
    return String(value);
  }
  if (field.type === "list" || field.repeater) {
    if (Array.isArray(value)) return value;
    if (value == null || value === "") return [];
    return [value];
  }
  if (field.type === "form") {
    if (field.repeater) {
      if (Array.isArray(value)) return value;
      if (value && typeof value === "object") return [value];
      return [];
    }
    if (Array.isArray(value)) return value[0] || {};
    if (value && typeof value === "object") return value;
    return {};
  }
  if (Array.isArray(value)) return value.join("\n");
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function migrateDocument(doc, plan, options) {
  const keepUnknown = !options || options.keepUnknown !== false;
  const keepRemoved = options && options.keepRemoved;
  if (!doc || typeof doc !== "object") return { doc, changes: [] };
  if (plan.formkey && doc.form && doc.form !== plan.formkey) {
    return { doc, changes: [] };
  }

  const changes = [];
  const next = { form: doc.form, text: doc.text };
  const skip = new Set(["form", "text"]);
  const incoming = {};

  for (const [key, value] of Object.entries(doc)) {
    if (skip.has(key)) continue;
    const dest = plan.renames[key] || key;
    if (dest !== key) changes.push({ op: "rename", from: key, to: dest });
    incoming[dest] = value;
  }

  const known = new Set(plan.fields.map((field) => field.key));
  for (const field of plan.fields) {
    if (!(field.key in incoming)) continue;
    const before = incoming[field.key];
    const after = coerceValue(before, field);
    next[field.key] = after;
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      changes.push({ op: "coerce", key: field.key, type: field.type });
    }
  }

  for (const [key, value] of Object.entries(incoming)) {
    if (key in next) continue;
    if (plan.removed.includes(key) && !keepRemoved) {
      changes.push({ op: "drop", key });
      continue;
    }
    if (keepUnknown || known.has(key) || keepRemoved) next[key] = value;
  }

  return { doc: next, changes };
}

function planIsEmpty(plan) {
  return (
    Object.keys(plan.renames).length === 0 &&
    plan.removed.length === 0 &&
    plan.typeChanges.length === 0
  );
}
