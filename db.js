const DB_NAME = "formdef";
const DB_VERSION = 1;

function openDb() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new Error("IndexedDB is not available"));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("docs")) {
        db.createObjectStore("docs", { keyPath: "form" });
      }
      if (!db.objectStoreNames.contains("formdefs")) {
        db.createObjectStore("formdefs", { keyPath: "formkey" });
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta");
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function requestValue(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function allFromStore(store) {
  return requestValue(store.getAll());
}

async function dbLoad(db) {
  const tx = db.transaction(["docs", "formdefs", "meta"], "readonly");
  const [docs, formdefs, lists, lastForm, seeded] = await Promise.all([
    allFromStore(tx.objectStore("docs")),
    allFromStore(tx.objectStore("formdefs")),
    requestValue(tx.objectStore("meta").get("lists")),
    requestValue(tx.objectStore("meta").get("lastForm")),
    requestValue(tx.objectStore("meta").get("seeded")),
  ]);
  return { docs, formdefs, lists, lastForm, seeded };
}

async function dbSeed(db, payload) {
  const tx = db.transaction(["docs", "formdefs", "meta"], "readwrite");
  const formdefs = tx.objectStore("formdefs");
  for (const def of Object.values(payload.formdefs || {})) formdefs.put(def);
  if (payload.draft) tx.objectStore("docs").put(payload.draft);
  const meta = tx.objectStore("meta");
  meta.put(payload.lists || {}, "lists");
  meta.put(payload.draft?.form || "persoon", "lastForm");
  meta.put(true, "seeded");
  await new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function dbSaveWorkspace(db, workspace) {
  const tx = db.transaction(["docs", "formdefs", "meta"], "readwrite");
  const docs = tx.objectStore("docs");
  for (const doc of workspace.docs) docs.put(doc);
  const formdefs = tx.objectStore("formdefs");
  for (const def of workspace.formdefs) formdefs.put(def);
  const meta = tx.objectStore("meta");
  meta.put(workspace.lastForm, "lastForm");
  if (workspace.lists) meta.put(workspace.lists, "lists");
  await new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
