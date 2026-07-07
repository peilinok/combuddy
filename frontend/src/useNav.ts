import { ref } from "vue";

export type View = "dashboard" | "library" | "workflows" | "cleanup" | "settings";
export type CleanupTab = "unreferenced" | "duplicates";

export const view = ref<View>("dashboard");
export const cleanupTab = ref<CleanupTab>("unreferenced");
