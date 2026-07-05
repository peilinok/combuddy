import { ref } from "vue";
import { fetchModels, fetchModel, getSettings } from "./api";

export function useLibrary() {
  const models = ref<any[]>([]);
  const selected = ref<any | null>(null);
  const search = ref(""); const flag = ref("");
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

  return { models, selected, search, flag, revealed, lightbox, error, load, openDetail,
    shouldBlur, reveal, openLightbox, closeLightbox };
}
