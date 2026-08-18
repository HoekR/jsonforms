/** Formdef → search roles and an Elasticsearch mapping. */

function mainFormdefs(formdefs) {
  return Object.values(formdefs || {}).filter(
    (def) => def && def.level === "main" && def.formkey && def.formkey !== "formdef"
  );
}

function searchSchema(formdefs) {
  const facets = [];
  const seen = new Set();
  const namefield = {};
  for (const def of mainFormdefs(formdefs)) {
    if (def.namefield) namefield[def.formkey] = def.namefield;
    for (const field of def.fields || []) {
      if (field.type !== "list" && field.type !== "choice") continue;
      if (seen.has(field.key)) continue;
      seen.add(field.key);
      facets.push({
        key: field.key,
        title: field.title || field.key,
        contents_key: field.contents_key || null,
      });
    }
  }
  return { facets, namefield };
}

function elasticsearchProperty(field, nameKeys) {
  if (nameKeys.has(field.key)) {
    return { type: "text", fields: { raw: { type: "keyword" } } };
  }
  if (field.type === "list" || field.type === "choice") return { type: "keyword" };
  if (field.type === "bool") return { type: "boolean" };
  if (field.type === "form") {
    return field.repeater ? { type: "nested" } : { type: "object", enabled: true };
  }
  return { type: "text" };
}

function elasticsearchMapping(formdefs) {
  const nameKeys = new Set(
    mainFormdefs(formdefs)
      .map((def) => def.namefield)
      .filter(Boolean)
  );
  const properties = {
    form: { type: "keyword" },
    text: { type: "text" },
  };
  for (const def of Object.values(formdefs || {})) {
    for (const field of def.fields || []) {
      if (!field.key || field.key === "text" || properties[field.key]) continue;
      properties[field.key] = elasticsearchProperty(field, nameKeys);
    }
  }
  return { mappings: { properties } };
}
