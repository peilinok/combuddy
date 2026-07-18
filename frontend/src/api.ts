export class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, detail: string | null) {
    super("HTTP " + status + (detail ? " · " + detail : ""));
    this.status = status;
    this.detail = detail;
  }
}

async function jsonOrThrow(r: Response) {
  if (!r.ok) {
    let detail: unknown = null;
    try {
      const body = await r.json();
      detail = body?.reason ?? body?.error ?? body?.detail ?? null;
    } catch { /* 非 JSON 错误体：仅保留状态码 */ }
    throw new ApiError(r.status, typeof detail === "string" ? detail : null);
  }
  return r.json();
}

export const fetchStats = () => fetch("/api/stats").then(jsonOrThrow);
export const postScan = () => fetch("/api/scan", { method: "POST" }).then(jsonOrThrow);
export const getRoots = () => fetch("/api/roots").then(jsonOrThrow);
export const setRoots = (roots: unknown[]) =>
  fetch("/api/roots", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roots }) }).then(jsonOrThrow);
export const deleteRoot = (id: number) =>
  fetch(`/api/roots/${id}`, { method: "DELETE" }).then(jsonOrThrow);

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
export const fetchDuplicates = () => fetch("/api/cleanup/duplicates").then(jsonOrThrow);

export const postScanCancel = () => fetch("/api/scan/cancel", { method: "POST" }).then(jsonOrThrow);
export const getSettings = () => fetch("/api/settings").then(jsonOrThrow);
export const setSettings = (s: Record<string, unknown>) =>
  fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(s) }).then(jsonOrThrow);
export const fetchDetect = () => fetch("/api/detect").then(jsonOrThrow);

// 导出是二进制:绝不能走 jsonOrThrow(它末尾无条件 r.json(),会把 zip 当 JSON 解析)。
// 也不能只用 <a download>——那是浏览器黑盒,后端 404/409 前端读不到,用户会下到假 zip。
export async function fetchWorkflowBundle(id: number): Promise<Blob> {
  const r = await fetch(`/api/workflows/${id}/bundle`);
  if (!r.ok) {
    let detail: unknown = null;
    try { detail = (await r.json())?.reason ?? null; } catch { /* 非 JSON 错误体 */ }
    throw new ApiError(r.status, typeof detail === "string" ? detail : null);
  }
  return r.blob();
}

// 请求体是二进制、响应是 report JSON → 复用 jsonOrThrow 正确。
// 直接把 File 当 body 发原始字节,后端 request.stream() 收,无需 multipart。
export const verifyManifest = (file: File | Blob) =>
  fetch("/api/manifest/verify", { method: "POST", body: file }).then(jsonOrThrow);

export const fetchLocate = (p: Record<string, string>) =>
  fetch("/api/locate" + (qs(p) ? "?" + qs(p) : "")).then(jsonOrThrow);

export const postDownload = (spec: any) => fetch("/api/download", { method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(spec) }).then(jsonOrThrow);
export const postDownloadCancel = () => fetch("/api/download/cancel", { method: "POST" }).then(jsonOrThrow);
