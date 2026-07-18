<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { getRoots } from "./api";
import { useTheme } from "./useTheme";
import { view, type View } from "./useNav";
import { demo, useDemo } from "./useDemo";
import { update, useDesktop } from "./useDesktop";
import { useScanStatus } from "./useScanStatus";
import { useDownload } from "./useDownload";
import DashboardView from "./components/DashboardView.vue";
import LibraryView from "./components/LibraryView.vue";
import WorkflowView from "./components/WorkflowView.vue";
import CleanupView from "./components/CleanupView.vue";
import SettingsView from "./components/SettingsView.vue";
import RootsSetup from "./components/RootsSetup.vue";

useTheme(); // 接管换肤(首屏脚本已上好初始主题)
useDemo(); // 一次性拉取 demo 标志,供本组件横幅 + 扫描按钮共享
useDesktop(); // 一次性接入桌面壳(isDesktop/自动更新提示),供本组件更新横幅使用
const { scanning: scanActive } = useScanStatus();
const { downloading, progress, cancelDownload } = useDownload();
const { t } = useI18n();
const { openExternal } = useDesktop();
function openExternalOrNav(u: string) { openExternal(u).then((ok) => { if (!ok) window.open(u, "_blank"); }); }
const configured = ref(true);
const views = { dashboard: DashboardView, library: LibraryView, workflows: WorkflowView,
  cleanup: CleanupView, settings: SettingsView };
const items = computed(() => ([
  { key: "dashboard", label: t("nav.dashboard"), icon: "pi pi-chart-bar" },
  { key: "library", label: t("nav.library"), icon: "pi pi-images" },
  { key: "workflows", label: t("nav.workflows"), icon: "pi pi-sitemap" },
  { key: "cleanup", label: t("nav.cleanup"), icon: "pi pi-trash" },
  { key: "settings", label: t("nav.settings"), icon: "pi pi-cog" },
] as const).map((n) => ({ label: n.label, icon: n.icon,
  class: view.value === n.key ? "cb-nav-active" : "", command: () => (view.value = n.key as View) })));
onMounted(async () => { const r = await getRoots(); configured.value = (r.roots?.length ?? 0) > 0; });
</script>
<template>
  <div class="min-h-screen flex bg-surface-ground text-color">
    <aside class="w-52 bg-surface-card border-r border-surface-border p-3 shrink-0">
      <div class="font-semibold px-2">combuddy</div>
      <div class="text-[10px] text-color-secondary px-2 mb-4">{{ t("common.subtitle") }}</div>
      <Menu :model="items" class="w-full border-0 bg-transparent" />
      <button v-if="scanActive" @click="view = 'dashboard'"
        class="mt-2 w-full flex items-center gap-2 px-3 py-2 text-xs text-primary rounded-lg bg-primary/10">
        <i class="pi pi-spin pi-spinner"></i>
        <span>{{ t("nav.scanBadge") }}</span>
      </button>
      <div v-if="downloading" class="mt-2 w-full flex items-center justify-between gap-2 px-3 py-2 text-xs text-primary rounded-lg bg-primary/10">
        <span class="flex items-center gap-2 truncate"><i class="pi pi-spin pi-spinner shrink-0"></i>{{ t("download.badge", { progress }) }}</span>
        <button @click="cancelDownload" :title="t('download.cancel')" class="text-color-secondary hover:text-orange-400 shrink-0">
          <i class="pi pi-times text-xs"></i></button>
      </div>
    </aside>
    <main class="flex-1 p-6 overflow-auto">
      <div v-if="update" class="mb-4 px-3 py-2 rounded-lg bg-primary/20 text-primary text-xs font-medium flex justify-between">
        <span>{{ t("desktop.updateBanner", { v: update.version }) }}</span>
        <a :href="update.url" @click.prevent="openExternalOrNav(update.url)" class="underline cursor-pointer">{{ t("desktop.updateGet") }}</a>
      </div>
      <div v-if="demo" class="mb-4 px-3 py-2 rounded-lg bg-primary/20 text-primary text-xs font-medium">
        {{ t("demo.banner") }}
      </div>
      <RootsSetup v-if="!configured" @done="configured = true" />
      <component v-else :is="views[view]" />
    </main>
  </div>
</template>
<style>
.cb-nav-active .p-menuitem-link { background: var(--surface-hover); }
.cb-nav-active .p-menuitem-text, .cb-nav-active .p-menuitem-icon { color: var(--primary-color) !important; }
</style>
