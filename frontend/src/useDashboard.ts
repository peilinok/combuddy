import { postScan, postScanCancel } from "./api";
import { useScanStatus } from "./useScanStatus";

export function useDashboard() {
  const { stats, scanning, error, refresh } = useScanStatus();

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

  return { stats, scanning, error, startScan, cancelHash, refresh };
}
