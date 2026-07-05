<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getRoots } from "./api";
import DashboardView from "./components/DashboardView.vue";
import LibraryView from "./components/LibraryView.vue";
import WorkflowView from "./components/WorkflowView.vue";
import CleanupView from "./components/CleanupView.vue";
import RootsSetup from "./components/RootsSetup.vue";

const configured = ref(true);
const view = ref<"dashboard" | "library" | "workflows" | "cleanup">("dashboard");
const nav = [
  { key: "dashboard", label: "Dashboard" }, { key: "library", label: "模型库" },
  { key: "workflows", label: "Workflow 对应" }, { key: "cleanup", label: "清理中心" },
] as const;
const views = { dashboard: DashboardView, library: LibraryView, workflows: WorkflowView, cleanup: CleanupView };
onMounted(async () => { const r = await getRoots(); configured.value = (r.roots?.length ?? 0) > 0; });
</script>
<template>
  <div class="min-h-screen flex text-[#e8e8ea]">
    <aside class="w-44 bg-[#1e1e24] p-4 shrink-0">
      <div class="font-semibold">combuddy</div>
      <div class="text-[10px] text-[#7a7a82] mb-6">模型与依赖管家</div>
      <div v-for="n in nav" :key="n.key" @click="view = n.key"
        :class="['px-3 py-2 rounded-lg text-sm cursor-pointer mb-1',
          view === n.key ? 'bg-[#1b3d29] text-[#4ade80] font-semibold' : 'text-[#9a9aa2] hover:text-[#e8e8ea]']">
        {{ n.label }}
      </div>
      <div class="mt-2 text-sm text-[#5c5c64]">下载中心 <span class="text-[10px]">以后</span></div>
    </aside>
    <main class="flex-1 p-6">
      <RootsSetup v-if="!configured" @done="configured = true" />
      <component v-else :is="views[view]" />
    </main>
  </div>
</template>
