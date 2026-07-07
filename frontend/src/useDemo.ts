import { ref } from "vue";
import { fetchStats } from "./api";

// 模块级单例状态 —— App.vue 触发一次性加载,其余调用者(如扫描按钮)直接读同一份 ref
export const demo = ref(false);
let started = false;

export function useDemo() {
  if (!started) {
    started = true;
    fetchStats().then((s) => { demo.value = !!s.demo; }).catch(() => {});
  }
  return { demo };
}
