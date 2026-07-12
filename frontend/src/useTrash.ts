import { ref, computed } from "vue";
import { fetchTrash, postRestore } from "./api";

export function useTrash() {
  const items = ref<any[]>([]);
  const error = ref<string | null>(null);
  const restoring = ref(false);
  const lastRestore = ref<{ restored: number; conflict: number; error: number } | null>(null);
  const totalBytes = computed(() => items.value.reduce((s: number, t: any) => s + (t.size ?? 0), 0));
  let loadSeq = 0;

  async function load() {
    const my = ++loadSeq;
    try {
      const r = await fetchTrash();
      if (my === loadSeq) { items.value = r.trash; error.value = null; }
    } catch (e) { if (my === loadSeq) error.value = String(e); }
  }
  async function restore(ids: number[]) {
    if (restoring.value) return;
    restoring.value = true;
    lastRestore.value = null;
    error.value = null;
    ++loadSeq;
    try {
      const r = await postRestore(ids);
      lastRestore.value = { restored: r.restored?.length ?? 0, conflict: r.conflict?.length ?? 0, error: r.error?.length ?? 0 };
      await load();
    } catch (e) { error.value = String(e); }
    finally { restoring.value = false; }
  }
  return { items, error, restoring, lastRestore, totalBytes, load, restore };
}
