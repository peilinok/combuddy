async function jsonOrThrow(r: Response) {
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

export const fetchStats = () => fetch("/api/stats").then(jsonOrThrow);
export const postScan = () => fetch("/api/scan", { method: "POST" }).then(jsonOrThrow);
export const getRoots = () => fetch("/api/roots").then(jsonOrThrow);
export const setRoots = (roots: unknown[]) =>
  fetch("/api/roots", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roots }) }).then(jsonOrThrow);

const qs = (o: Record<string, string>) =>
  Object.entries(o).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
export const fetchModels = (p: Record<string, string> = {}) =>
  fetch("/api/models" + (qs(p) ? "?" + qs(p) : "")).then(jsonOrThrow);
export const fetchModel = (id: number) => fetch(`/api/models/${id}`).then(jsonOrThrow);
export const fetchWorkflows = () => fetch("/api/workflows").then(jsonOrThrow);
export const fetchWorkflowResolution = (id: number) => fetch(`/api/workflows/${id}`).then(jsonOrThrow);
export const fetchUnreferenced = () => fetch("/api/unreferenced").then(jsonOrThrow);
export const postTrash = (model_ids: number[]) =>
  fetch("/api/cleanup/trash", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_ids }) }).then(jsonOrThrow);
export const fetchTrash = () => fetch("/api/cleanup/trash").then(jsonOrThrow);
export const postRestore = (trash_ids: number[]) =>
  fetch("/api/cleanup/restore", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trash_ids }) }).then(jsonOrThrow);
