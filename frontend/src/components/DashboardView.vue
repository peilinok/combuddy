<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";
import { useDashboard } from "../useDashboard";
import { humanSize } from "../format";
import TypePanel from "./TypePanel.vue";
const { stats, scanning, error, startScan, cancelHash,
  refresh, startPolling, stopPolling } = useDashboard();
onMounted(async () => { await refresh(); startPolling(); });
onUnmounted(stopPolling);

const tiles = computed(() => [
  { label: "模型", icon: "pi pi-images", value: stats.value.model_count, sub: humanSize(stats.value.total_size) },
  { label: "工作流", icon: "pi pi-sitemap", value: stats.value.workflow_count },
  { label: "总大小", icon: "pi pi-database", value: humanSize(stats.value.total_size) },
  { label: "未被引用", icon: "pi pi-exclamation-triangle", value: stats.value.unreferenced_count, sub: "可清理", warn: true },
]);

function cov(c: any, key: string) { const done = c?.[key] ?? 0, total = c?.total ?? 0;
  return { done, total, pct: total ? Math.round(100 * done / total) : 0 }; }
const knobs = computed(() => [
  { label: "base 识别", ...cov(stats.value.base_coverage, "done") },
  { label: "sha256 指纹", ...cov(stats.value.hash_coverage, "hashed") },
  { label: "Civitai 识别", ...cov(stats.value.civitai_coverage, "identified") },
]);
</script>
<template>
  <div>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-semibold">Dashboard</h1>
      <button @click="startScan" :disabled="scanning"
        class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-50">
        {{ scanning ? (stats.scan?.phase === 'hashing' ? "计算指纹中…" : stats.scan?.phase === 'enriching' ? "联网识别中…" : "扫描中…") : "扫描 / 刷新" }}
      </button>
    </div>
    <div class="grid grid-cols-4 gap-3 mb-4">
      <Card v-for="s in tiles" :key="s.label"><template #content>
        <div class="flex items-center gap-3">
          <i :class="s.icon" class="text-2xl text-primary"></i>
          <div><div class="text-2xl font-bold" :class="s.warn ? 'text-orange-400' : 'text-color'">{{ s.value }}</div>
            <div class="text-xs text-color-secondary">{{ s.label }}<span v-if="s.sub"> · {{ s.sub }}</span></div></div>
        </div></template></Card>
    </div>
    <div class="grid grid-cols-3 gap-3 mb-4">
      <Card v-for="k in knobs" :key="k.label"><template #content>
        <div class="flex flex-col items-center">
          <Knob :modelValue="k.pct" :min="0" :max="100" readonly valueTemplate="{value}%" :size="110" />
          <div class="text-sm text-color-secondary mt-1">{{ k.label }}</div>
          <div class="text-xs text-color-secondary">{{ k.done }}/{{ k.total }}</div>
        </div></template></Card>
    </div>
    <TypePanel :byType="stats.by_type" />
  </div>
</template>
