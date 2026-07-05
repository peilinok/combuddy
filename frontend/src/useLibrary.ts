import { computed, ref } from "vue";
import { fetchModels, fetchModel, getSettings } from "./api";

export function useLibrary() {
  const models = ref<any[]>([]);
  const selected = ref<any | null>(null);
  const search = ref(""); const flag = ref("");
  const layout = ref<"grid" | "list" | "folder">("grid");
  const nsfwThreshold = ref(1);
  const revealed = ref<Set<number>>(new Set());
  const lightbox = ref<any | null>(null);
  const error = ref<string | null>(null);

  async function load() {
    try {
      const [m, s] = await Promise.all([
        fetchModels({ search: search.value, flag: flag.value }), getSettings()]);
      models.value = m.models; nsfwThreshold.value = s.nsfw_blur_threshold ?? 1; error.value = null;
    } catch (e) { error.value = String(e); }
  }
  async function openDetail(id: number) {
    if (selected.value?.id === id) { selected.value = null; return; }
    try { selected.value = await fetchModel(id); } catch (e) { error.value = String(e); }
  }
  const shouldBlur = (level: number | null) => (level ?? 0) > nsfwThreshold.value;
  const reveal = (id: number) => { revealed.value = new Set(revealed.value).add(id); };
  const openLightbox = (m: any) => { lightbox.value = m; };
  const closeLightbox = () => { lightbox.value = null; };
  const treeNodes = computed(() => {
    const byType: Record<string, any[]> = {};
    for (const m of models.value) (byType[m.dir_type] ||= []).push(m);
    return Object.entries(byType).map(([type, ms]) => ({
      key: type, label: `${type} (${ms.length})`, icon: "pi pi-folder",
      children: ms.map((m) => ({ key: `${type}/${m.id}`, label: m.civitai_name || m.display_name || m.filename,
        icon: "pi pi-box", data: m, leaf: true })),
    }));
  });

  return { models, selected, search, flag, layout, revealed, lightbox, error, load, openDetail,
    shouldBlur, reveal, openLightbox, closeLightbox, treeNodes };
}
