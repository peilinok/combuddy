import { ref } from "vue";
import { getSettings, setSettings, getRoots, setRoots } from "./api";

export function useSettings() {
  const settings = ref<any>({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
  const roots = ref<any[]>([]);
  const error = ref<string | null>(null);
  async function load() {
    try { const [s, r] = await Promise.all([getSettings(), getRoots()]);
      settings.value = s; roots.value = r.roots ?? []; error.value = null;
    } catch (e) { error.value = String(e); }
  }
  async function save(patch: Record<string, unknown>) {
    try { settings.value = await setSettings(patch); } catch (e) { error.value = String(e); }
  }
  async function addRoot(kind: string, path: string) {
    try { await setRoots([{ kind, path, source: "manual" }]); const r = await getRoots(); roots.value = r.roots ?? []; }
    catch (e) { error.value = String(e); }
  }
  return { settings, roots, error, load, save, addRoot };
}
