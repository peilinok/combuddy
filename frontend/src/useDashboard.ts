import { ref } from "vue";
import { fetchStats, postScan, postScanCancel } from "./api";

export function useDashboard() {
  const stats = ref<any>({ model_count: 0, total_size: 0, workflow_count: 0,
    base_coverage: { done: 0, total: 0 }, hash_coverage: { hashed: 0, total: 0 },
    civitai_coverage: { identified: 0, total: 0 },
    unreferenced_count: 0, by_type: [], scanning: false, scan: { phase: "idle" } });
  const loading = ref(false);
  const scanning = ref(false);
  const error = ref<string | null>(null);
  let timer: number | undefined;

  async function refresh() {
    loading.value = true;
    try {
      stats.value = await fetchStats();
      scanning.value = !!stats.value.scanning;
      error.value = null;
    } catch (e) {
      error.value = String(e);
    } finally { loading.value = false; }
  }
  async function startScan() {
    try {
      await postScan();
    } catch (e) {
      error.value = String(e);
      return;
    }
    await refresh();
  }
  async function cancelHash() {
    try { await postScanCancel(); } catch (e) { error.value = String(e); }
    await refresh();
  }
  function startPolling(ms = 1500) {
    stopPolling();
    timer = window.setInterval(refresh, ms);
  }
  function stopPolling() { if (timer) { clearInterval(timer); timer = undefined; } }

  return { stats, loading, scanning, error, startScan, cancelHash,
    refresh, startPolling, stopPolling };
}
