import { ref } from "vue";
import { fetchStats } from "./api";

// 模块级单例(仿 useDemo/useTheme)。桌面壳把 window.pywebview 注入得比页面加载晚,
// 故既查当下也监听一次 pywebviewready。
export const isDesktop = ref(false);
export const update = ref<{ version: string; url: string } | null>(null);
let started = false;

function bridge(): any {
  return typeof window !== "undefined" ? (window as any).pywebview?.api : undefined;
}

export function useDesktop() {
  if (!started) {
    started = true;
    if (typeof window !== "undefined") {
      if ((window as any).pywebview) isDesktop.value = true;
      else window.addEventListener?.("pywebviewready", () => { isDesktop.value = true; });
    }
    // give the update-check thread a moment, then read the flag once
    setTimeout(() => { fetchStats().then((s: any) => { if (s.update) update.value = s.update; }).catch(() => {}); }, 5000);
  }
  return {
    isDesktop, update,
    async pickFolder(): Promise<string | null> {
      const b = bridge(); return b?.pick_folder ? await b.pick_folder() : null;
    },
    async reveal(path: string): Promise<boolean> {
      const b = bridge(); return b?.reveal ? await b.reveal(path) : false;
    },
    async openExternal(url: string): Promise<boolean> {
      const b = bridge(); return b?.open_external ? await b.open_external(url) : false;
    },
  };
}
