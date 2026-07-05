<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { getRoots } from "./api";
import { useTheme } from "./useTheme";
import DashboardView from "./components/DashboardView.vue";
import LibraryView from "./components/LibraryView.vue";
import WorkflowView from "./components/WorkflowView.vue";
import CleanupView from "./components/CleanupView.vue";
import SettingsView from "./components/SettingsView.vue";
import RootsSetup from "./components/RootsSetup.vue";

useTheme(); // 接管换肤(首屏脚本已上好初始主题)
const configured = ref(true);
type View = "dashboard" | "library" | "workflows" | "cleanup" | "settings";
const view = ref<View>("dashboard");
const views = { dashboard: DashboardView, library: LibraryView, workflows: WorkflowView,
  cleanup: CleanupView, settings: SettingsView };
const items = computed(() => ([
  { key: "dashboard", label: "Dashboard", icon: "pi pi-chart-bar" },
  { key: "library", label: "模型库", icon: "pi pi-images" },
  { key: "workflows", label: "Workflow 对应", icon: "pi pi-sitemap" },
  { key: "cleanup", label: "清理中心", icon: "pi pi-trash" },
  { key: "settings", label: "设置", icon: "pi pi-cog" },
] as const).map((n) => ({ label: n.label, icon: n.icon,
  class: view.value === n.key ? "cb-nav-active" : "", command: () => (view.value = n.key as View) })));
onMounted(async () => { const r = await getRoots(); configured.value = (r.roots?.length ?? 0) > 0; });
</script>
<template>
  <div class="min-h-screen flex bg-surface-ground text-color">
    <aside class="w-52 bg-surface-card border-r border-surface-border p-3 shrink-0">
      <div class="font-semibold px-2">combuddy</div>
      <div class="text-[10px] text-color-secondary px-2 mb-4">模型与依赖管家</div>
      <Menu :model="items" class="w-full border-0 bg-transparent" />
    </aside>
    <main class="flex-1 p-6 overflow-auto">
      <RootsSetup v-if="!configured" @done="configured = true" />
      <component v-else :is="views[view]" />
    </main>
  </div>
</template>
<style>
.cb-nav-active .p-menuitem-link { background: var(--surface-hover); }
.cb-nav-active .p-menuitem-text, .cb-nav-active .p-menuitem-icon { color: var(--primary-color) !important; }
</style>
