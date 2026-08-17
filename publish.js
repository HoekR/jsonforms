const CORPUS_KIND = "formdef-corpus";

function isCorpus(data) {
  return Boolean(data && data.kind === CORPUS_KIND && Array.isArray(data.documents));
}

function buildCorpus(parts) {
  return {
    kind: CORPUS_KIND,
    published: parts.published || new Date().toISOString(),
    formdefs: parts.formdefs || {},
    lists: parts.lists || {},
    documents: parts.documents || [],
  };
}
