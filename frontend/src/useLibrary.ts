import { computed, ref, watch } from "vue";
import { fetchModels, fetchModel, getSettings } from "./api";

export function useLibrary() {
  const models = ref<any[]>([]);
  const selected = ref<any | null>(null);
  const search = ref(""); const flag = ref("");
  const layout = ref<"grid" | "list">("grid");
  const typeFilter = ref("");
  const pageFirst = ref(0);
  const collapsed = ref(false);
  const nsfwThreshold = ref(1);
  const revealed = ref<Set<number>>(new Set());
  const lightbox = ref<any | null>(null);
  const error = ref<string | null>(null);
  const loading = ref(false);
  let seq = 0;
  let detailSeq = 0;
  let settingsPromise: Promise<void> | null = null;
  let debounceTimer: number | undefined;

  async function load() {
    const my = ++seq;
    loading.value = true;
    if (!settingsPromise) {
      settingsPromise = getSettings()
        .then((s) => { nsfwThreshold.value = s.nsfw_blur_threshold ?? 1; })
        .catch((e) => { settingsPromise = null; throw e; });
    }
    try {
      const [m] = await Promise.all([
        fetchModels({ search: search.value, flag: flag.value }), settingsPromise]);
      if (my !== seq) return;
      models.value = m.models; error.value = null;
    } catch (e) { if (my === seq) error.value = String(e); }
    finally { if (my === seq) loading.value = false; }
  }
  function searchInput() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(load, 300);
  }
  async function openDetail(id: number) {
    const my = ++detailSeq;
    if (selected.value?.id === id) { selected.value = null; return; }
    try {
      const detail = await fetchModel(id);
      if (my !== detailSeq) return;
      selected.value = detail; error.value = null;
    } catch (e) { if (my === detailSeq) error.value = String(e); }
  }
  const shouldBlur = (level: number | null) => (level ?? 0) > nsfwThreshold.value;
  const reveal = (id: number) => { revealed.value = new Set(revealed.value).add(id); };
  const openLightbox = (m: any) => { lightbox.value = m; };
  const closeLightbox = () => { lightbox.value = null; };
  const typeCounts = computed(() => {
    const c: Record<string, number> = {};
    for (const m of models.value) c[m.dir_type] = (c[m.dir_type] ?? 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]).map(([dir_type, count]) => ({ dir_type, count }));
  });
  const visibleModels = computed(() => typeFilter.value ? models.value.filter((m) => m.dir_type === typeFilter.value) : models.value);
  watch([search, flag, typeFilter], () => { pageFirst.value = 0; });

  return { models, selected, search, flag, layout, revealed, lightbox, error, loading, load, searchInput, openDetail,
    shouldBlur, reveal, openLightbox, closeLightbox, typeFilter, pageFirst, collapsed, typeCounts, visibleModels };
}
