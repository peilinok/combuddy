import { ref } from "vue";
import { fetchLocate } from "./api";

// 模块级单例(仿 useManifest):LocateDialog.vue 与 WorkflowView.vue 共享同一份对话框状态。
// locate 对话框内无 in-app 导航(点候选走外链、不切 view),故不重蹈 manifest H8。
export const open = ref(false);
export const loading = ref(false);
export const mode = ref<"hash" | "name" | null>(null);
export const result = ref<any | null>(null);
export const error = ref<string | null>(null);
export const query = ref("");
export const target = ref<{ ref_string: string; dir_type?: string; sha256?: string } | null>(null);

const norm = (s: string) => s.replaceAll("\\", "/");
const fullBase = (rs: string) => norm(rs).split("/").pop() ?? rs;
function stem(rs: string): string {
  const b = fullBase(rs);
  const dot = b.lastIndexOf(".");
  return dot > 0 ? b.slice(0, dot) : b;      // 只去最后一段扩展名;无扩展名/CJK 原样
}
export function expectedPath(t: { ref_string: string; dir_type?: string }): string {
  const rel = norm(t.ref_string);
  return t.dir_type ? `${t.dir_type}/${rel}` : rel;
}
export function siteSearchUrl(): string {
  return "https://civitai.com/search/models?query=" + encodeURIComponent(query.value);
}

async function run(params: Record<string, string>) {
  loading.value = true; error.value = null; result.value = null;
  try { result.value = await fetchLocate(params); }
  catch (e: any) { error.value = typeof e?.detail === "string" ? e.detail : "unknown"; }
  finally { loading.value = false; }
}

export async function openFor(t: { ref_string: string; dir_type?: string; sha256?: string }) {
  target.value = t; query.value = stem(t.ref_string);
  mode.value = null; result.value = null; error.value = null; open.value = true;
  if (t.sha256) { mode.value = "hash"; await run({ sha256: t.sha256 }); }
  // 无 sha:不自动搜,停待搜索态 [H3]
}
export async function search() {
  const t = target.value; if (!t || !query.value) return;
  mode.value = "name";
  await run({ q: query.value, ref: fullBase(t.ref_string), dir_type: t.dir_type ?? "" });
}
export async function searchUnfiltered() {
  const t = target.value; if (!t || !query.value) return;
  mode.value = "name";
  await run({ q: query.value, ref: fullBase(t.ref_string), nofilter: "1" });
}
export async function fallbackToName() {
  const t = target.value; if (!t) return;
  query.value = stem(t.ref_string);
  await search();
}
export function close() { open.value = false; }

export function useLocate() {
  return { open, loading, mode, result, error, query, target,
           openFor, search, searchUnfiltered, fallbackToName, siteSearchUrl, expectedPath, close };
}
