<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";
import { useDashboard } from "../useDashboard";
import { humanSize } from "../format";
const { stats, scanning, error, startScan, cancelHash,
  refresh, startPolling, stopPolling } = useDashboard();
onMounted(async () => { await refresh(); startPolling(); });
onUnmounted(stopPolling);

const PALETTE_RING = ["#2ea043", "#3b82f6", "#a855f7", "#f59e0b", "#06b6d4", "#ef4444", "#8a8a93"];
function getVar(name: string) { return getComputedStyle(document.documentElement).getPropertyValue(name); }

const typeChart = computed(() => ({
  labels: (stats.value.by_type ?? []).map((t: any) => t.dir_type),
  datasets: [{ data: (stats.value.by_type ?? []).map((t: any) => t.size),
    backgroundColor: (stats.value.by_type ?? []).map((_: any, i: number) => PALETTE_RING[i % PALETTE_RING.length]) }],
}));
const chartOpts = { plugins: { legend: { position: "right", labels: { color: getVar("--text-color-secondary") } } },
  cutout: "62%" };

const PHASE_LABELS: Record<string, string> = { scanning: "扫描中…", workflows: "解析工作流中…", bases: "读头中…",
  hashing: "计算指纹中…", enriching: "联网识别中…" };
const phaseLabel = computed(() => PHASE_LABELS[stats.value.scan?.phase] ?? "扫描中…");
const phaseDone = computed(() => {
  const p = stats.value.scan?.phase;
  if (p === "hashing") return stats.value.scan?.hash_done ?? 0;
  if (p === "enriching") return stats.value.scan?.enrich_done ?? 0;
  return 0;
});
const phaseTotal = computed(() => {
  const p = stats.value.scan?.phase;
  if (p === "hashing") return stats.value.scan?.hash_total ?? 0;
  if (p === "enriching") return stats.value.scan?.enrich_total ?? 0;
  return 0;
});

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
    <div v-if="scanning" class="mb-4">
      <div class="text-sm text-color-secondary mb-1">{{ phaseLabel }}</div>
      <ProgressBar v-if="phaseTotal" :value="Math.round(100 * phaseDone / phaseTotal)" />
      <ProgressBar v-else mode="indeterminate" style="height:.5rem" />
      <Button label="取消" text @click="cancelHash" class="mt-2" v-if="stats.scan?.phase==='hashing' || stats.scan?.phase==='enriching'" />
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
    <Card class="mb-4"><template #title>按类型占用</template><template #content>
      <Chart type="doughnut" :data="typeChart" :options="chartOpts" class="max-h-72" />
    </template></Card>
  </div>
</template>
