import { ref } from "vue";
import { fetchDetect, setRoots, postScan } from "./api";

export interface Candidate {
  kind: "model" | "workflow"; path: string; source: string;
  label: string; model_count: number | null; count_capped: boolean;
}

export function useDetect() {
  const candidates = ref<Candidate[]>([]);
  const skipped = ref(0);
  const loading = ref(false);
  const error = ref("");
  const selected = ref<Set<string>>(new Set());

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
    if (!roots.length) return;
    await setRoots(roots);
    try { await postScan(); } catch { /* scan-start failure must not block */ }
  }

  return { candidates, skipped, loading, error, selected, load, toggle, confirm };
}
