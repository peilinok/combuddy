import { ref } from "vue";
import { fetchWorkflowBundle, verifyManifest } from "./api";

// 模块级单例(仿 useNav/useDesktop):App.vue 用 <component :is> 卸载式切换视图,
// 若 report 挂在组件实例上,用户点 model_id 去看详情再切回来报告就没了 [H8]
export const report = ref<any | null>(null);
export const error = ref<string | null>(null);
export const verifying = ref(false);

export const BODY_MAX = 10 * 1024 * 1024;   // 与后端 manifest.BODY_MAX 对齐

// 后端 reason 是稳定机器码,视图用 t("manifest.err_" + error) 映射 [M9]
function reasonOf(e: any): string {
  return typeof e?.detail === "string" ? e.detail : "unknown";
}

export async function exportBundle(workflowId: number, filename: string) {
  try {
    const blob = await fetchWorkflowBundle(workflowId);
    const url = URL.createObjectURL(blob);     // 原生下载,不引入 file-saver [L5]
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    error.value = null;
  } catch (e) {
    error.value = reasonOf(e);
  }
}

export async function verifyBundle(file: File) {
  report.value = null;   // 开始新核对:先清旧报告,否则失败/too_large 时旧报告会与新错误横幅同屏 [审查]
  if (file.size > BODY_MAX) { error.value = "too_large"; return; }   // 本地预检,不白传 [M10]
  verifying.value = true;
  try {
    report.value = await verifyManifest(file);
    error.value = null;
  } catch (e) {
    error.value = reasonOf(e);
  } finally {
    verifying.value = false;
  }
}

export function useManifest() {
  return { report, error, verifying, exportBundle, verifyBundle };
}
