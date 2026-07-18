import { computed, ref } from "vue";
import { stats, downloading, refresh } from "./useScanStatus";
import { postDownload, postDownloadCancel } from "./api";
export const error = ref<string | null>(null);      // 同步失败(跨源 403/已在下载 409)——postDownload reject
export const progress = computed(() => {
  const d = stats.value.download; return d?.total ? Math.round((d.downloaded / d.total) * 100) : 0;
});
// dismissedRevision:resetError() 记下调用时的 download.revision,用来压制上一轮残留的后台失败码——
// stats.download.error 是全局态,不知道自己是哪个 target 的失败,只能靠 revision 变没变判断"是否还相关"
// (同 useScanStatus 的 scanRevision 用法)[review Important I-4]
const dismissedRevision = ref(-1);
// 后台线程失败(9 个码:sha_mismatch/auth/disk_full/...)只写进 DOWNLOAD_STATUS.error,经 /api/stats.download
// 暴露;Promise 从不 reject。二者合并成单一展示源,否则用户看不到任何失败文案 [B2]。
export const downloadError = computed(() => {
  if (error.value) return error.value;
  const d = stats.value.download;
  return d?.error && d.revision !== dismissedRevision.value ? d.error : null;
});
export async function startDownload(spec: any) {
  error.value = null;
  try { await postDownload(spec); await refresh(); }
  catch (e: any) { error.value = typeof e?.detail === "string" ? e.detail : "unknown"; }
}
export async function cancelDownload() { try { await postDownloadCancel(); } catch { /* 忽略 */ } }
// openFor 切 target 时调用:清同步错误 + 把当前 revision 记为"已读",压掉上一个 target 残留的失败码 [I-4]
export function resetError() { error.value = null; dismissedRevision.value = stats.value.download?.revision ?? -1; }
export function useDownload() {
  return { downloading, progress, error, downloadError, startDownload, cancelDownload, resetError };
}
