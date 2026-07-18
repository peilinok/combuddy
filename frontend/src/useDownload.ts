import { computed, ref } from "vue";
import { stats, downloading, refresh } from "./useScanStatus";
import { postDownload, postDownloadCancel } from "./api";
export const error = ref<string | null>(null);      // 同步失败(跨源 403/已在下载 409)——postDownload reject
export const progress = computed(() => {
  const d = stats.value.download; return d?.total ? Math.round((d.downloaded / d.total) * 100) : 0;
});
// 后台线程失败(9 个码:sha_mismatch/auth/disk_full/...)只写进 DOWNLOAD_STATUS.error,经 /api/stats.download
// 暴露;Promise 从不 reject。二者合并成单一展示源,否则用户看不到任何失败文案 [B2]。
export const downloadError = computed(() => error.value ?? stats.value.download?.error ?? null);
export async function startDownload(spec: any) {
  error.value = null;
  try { await postDownload(spec); await refresh(); }
  catch (e: any) { error.value = typeof e?.detail === "string" ? e.detail : "unknown"; }
}
export async function cancelDownload() { try { await postDownloadCancel(); } catch { /* 忽略 */ } }
export function useDownload() { return { downloading, progress, error, downloadError, startDownload, cancelDownload }; }
