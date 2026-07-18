import { computed, ref } from "vue";
import { fetchStats } from "./api";

const ACTIVE_INTERVAL = 1500;
const IDLE_INTERVAL = 10000;

export const stats = ref<any>({ model_count: 0, total_size: 0, workflow_count: 0,
  base_coverage: { done: 0, total: 0 }, hash_coverage: { hashed: 0, total: 0 },
  civitai_coverage: { identified: 0, total: 0 },
  unreferenced_count: 0, duplicate_waste: 0, by_type: [], scanning: false, scan: { phase: "idle", revision: 0 } });
export const error = ref<string | null>(null);
export const scanning = computed(() => !!stats.value.scanning);
export const downloading = computed(() => !!stats.value.download?.running);
export const scanRevision = computed(() => stats.value.scan?.revision ?? 0);
let started = false;
let inFlight: Promise<void> | null = null;

export function refresh() {
  if (inFlight) return inFlight;
  inFlight = (async () => {
    try {
      stats.value = await fetchStats();
      error.value = null;
    } catch (e) {
      error.value = String(e);
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

function loop() {
  globalThis.setTimeout(async () => {
    if (typeof document === "undefined" || !document.hidden) await refresh();
    loop();
  }, (scanning.value || downloading.value) ? ACTIVE_INTERVAL : IDLE_INTERVAL);   // 下载中也提速 [H5]
}

export function useScanStatus() {
  if (!started) {
    started = true;
    refresh().then(loop);
  }
  return { stats, error, scanning, scanRevision, refresh };
}
