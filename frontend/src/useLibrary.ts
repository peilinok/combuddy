import { ref } from "vue";
import { fetchModels, fetchModel } from "./api";

export function useLibrary() {
  const models = ref<any[]>([]);
  const selected = ref<any | null>(null);
  const search = ref(""); const flag = ref("");
  const error = ref<string | null>(null);
  async function load() {
    try { models.value = (await fetchModels({ search: search.value, flag: flag.value })).models; error.value = null; }
    catch (e) { error.value = String(e); }
  }
  async function openDetail(id: number) {
    if (selected.value?.id === id) { selected.value = null; return; }
    try { selected.value = await fetchModel(id); } catch (e) { error.value = String(e); }
  }
  return { models, selected, search, flag, load, openDetail, error };
}
