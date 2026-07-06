<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { useDashboard } from "../useDashboard";
import { humanSize } from "../format";
const { t } = useI18n();
const { stats, scanning, error, startScan, cancelHash,
  refresh, startPolling, stopPolling } = useDashboard();
onMounted(async () => { await refresh(); startPolling(); });
onUnmounted(stopPolling);

const byTypeRows = computed(() => {
  const rows = (stats.value.by_type ?? []).map((t: any) => ({ dir_type: t.dir_type, size: t.size }));
  const max = Math.max(1, ...rows.map((r) => r.size));
  return rows.sort((a, b) => b.size - a.size).map((r) => ({ ...r, pct: Math.round((100 * r.size) / max) }));
});

const PHASE_LABELS: Record<string, string> = { scanning: "dashboard.phaseScanning", workflows: "dashboard.phaseWorkflows",
  bases: "dashboard.phaseBases", hashing: "dashboard.phaseHashing", enriching: "dashboard.phaseEnriching" };
const phaseLabel = computed(() => t(PHASE_LABELS[stats.value.scan?.phase] ?? "dashboard.phaseScanning"));
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
  { label: t("dashboard.models"), icon: "pi pi-images", value: stats.value.model_count, sub: humanSize(stats.value.total_size) },
  { label: t("dashboard.workflows"), icon: "pi pi-sitemap", value: stats.value.workflow_count },
  { label: t("dashboard.totalSize"), icon: "pi pi-database", value: humanSize(stats.value.total_size) },
  { label: t("dashboard.unreferenced"), icon: "pi pi-exclamation-triangle", value: stats.value.unreferenced_count, sub: t("dashboard.cleanable"), warn: true },
]);

function cov(c: any, key: string) { const done = c?.[key] ?? 0, total = c?.total ?? 0;
  return { done, total, pct: total ? Math.round(100 * done / total) : 0 }; }
const knobs = computed(() => [
  { label: t("dashboard.baseCoverage"), ...cov(stats.value.base_coverage, "done") },
  { label: t("dashboard.hashCoverage"), ...cov(stats.value.hash_coverage, "hashed") },
  { label: t("dashboard.civitaiCoverage"), ...cov(stats.value.civitai_coverage, "identified") },
]);
</script>
<template>
  <div>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-semibold">{{ t("dashboard.title") }}</h1>
      <button @click="startScan" :disabled="scanning"
        class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-50">
        {{ scanning ? (stats.scan?.phase === 'hashing' ? t("dashboard.hashing") : stats.scan?.phase === 'enriching' ? t("dashboard.enriching") : t("dashboard.scanning")) : t("dashboard.scan") }}
      </button>
    </div>
    <div v-if="scanning" class="mb-4">
      <div class="text-sm text-color-secondary mb-1">{{ phaseLabel }}</div>
      <ProgressBar v-if="phaseTotal" :value="Math.round(100 * phaseDone / phaseTotal)" />
      <ProgressBar v-else mode="indeterminate" style="height:.5rem" />
      <Button :label="t('dashboard.cancel')" text @click="cancelHash" class="mt-2" v-if="stats.scan?.phase==='hashing' || stats.scan?.phase==='enriching'" />
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
    <Card class="mb-4"><template #title>{{ t("dashboard.byType") }}</template><template #content>
      <div v-for="row in byTypeRows" :key="row.dir_type" class="flex items-center gap-3 mb-2">
        <div class="w-40 shrink-0 text-sm text-color-secondary truncate">{{ row.dir_type }}</div>
        <div class="flex-1 h-2.5 rounded-full bg-surface-hover overflow-hidden">
          <div class="h-full rounded-full bg-primary" :style="{ width: row.pct + '%' }"></div>
        </div>
        <div class="w-20 text-right text-xs text-color-secondary">{{ humanSize(row.size) }}</div>
      </div>
    </template></Card>
  </div>
</template>
