import { ref } from "vue";
import { fetchDetect, setRoots, postScan } from "./api";

export interface Candidate {
  kind: "model" | "workflow"; path: string; source: string;
  label: string; model_count: number | null; count_capped: boolean;
}

// 模块级单例(仿 useDesktop/useDemo)—— RootsSetup 触发一次 load(),DetectPanel 渲染同一份状态,
// 二者共享同一份 candidates/selected,而非各自独立的实例。
export const candidates = ref<Candidate[]>([]);
export const skipped = ref(0);
export const loading = ref(false);
export const error = ref("");
export const selected = ref<Set<string>>(new Set());

export function useDetect() {
  async function load() {
    loading.value = true; error.value = "";
    try {
      const r = await fetchDetect();
      candidates.value = r.candidates ?? [];
      skipped.value = r.skipped_config_mappings ?? 0;
      selected.value = new Set(candidates.value.map((c) => c.path));   // select-all default
    } catch (e: any) {
      error.value = String(e?.message ?? e);
      candidates.value = [];
    } finally {
      loading.value = false;
    }
  }

  function toggle(path: string) {
    const s = new Set(selected.value);
    s.has(path) ? s.delete(path) : s.add(path);
    selected.value = s;
  }

  async function confirm() {
    const roots = candidates.value
      .filter((c) => selected.value.has(c.path))
      .map((c) => ({ kind: c.kind, path: c.path, source: "detected" }));
    if (!roots.length) return false;
    try {
      const r = await setRoots(roots);
      if (!r.results?.some((result: any) => result.ok)) {
        error.value = r.results?.[0]?.reason ?? "not_a_directory";
        return false;
      }
      error.value = "";
      try { await postScan(); } catch { /* scan-start failure must not block */ }
      return true;
    } catch (e: any) {
      error.value = String(e?.message ?? e);
      return false;
    }
  }

  return { candidates, skipped, loading, error, selected, load, toggle, confirm };
}
