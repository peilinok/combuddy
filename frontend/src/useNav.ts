import { ref } from "vue";

export type View = "dashboard" | "library" | "workflows" | "cleanup" | "settings";
export type CleanupTab = "unreferenced" | "duplicates" | "trash";

export const view = ref<View>("dashboard");
export const cleanupTab = ref<CleanupTab>("unreferenced");

// 跨视图一次性传参:目标视图挂载时消费并清空
export const pendingWorkflowId = ref<number | null>(null);
export const pendingModelId = ref<number | null>(null);
