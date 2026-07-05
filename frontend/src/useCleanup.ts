import { ref, computed } from "vue";
import { fetchUnreferenced, postTrash } from "./api";

export function useCleanup() {
  const items = ref<any[]>([]);
  const selectedIds = ref<Set<number>>(new Set());
  const error = ref<string | null>(null);
  const selectedBytes = computed(() =>
    items.value.filter((m) => selectedIds.value.has(m.id)).reduce((s, m) => s + m.size, 0));
  async function load() {
    try { items.value = (await fetchUnreferenced()).models; selectedIds.value = new Set(); error.value = null; }
    catch (e) { error.value = String(e); }
  }
  function toggle(id: number) {
    const s = new Set(selectedIds.value);
    s.has(id) ? s.delete(id) : s.add(id);
    selectedIds.value = s;
  }
  async function trashSelected() {
    try { await postTrash([...selectedIds.value]); await load(); }
    catch (e) { error.value = String(e); }
  }
  return { items, selectedIds, selectedBytes, toggle, load, trashSelected, error };
}
