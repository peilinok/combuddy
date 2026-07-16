<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useWorkflows } from "../useWorkflows";
import { useManifest } from "../useManifest";
import { useDesktop } from "../useDesktop";
import { view, pendingWorkflowId, pendingModelId } from "../useNav";
const { t } = useI18n();
const { workflows, selected, load, select, error } = useWorkflows();
const { report, error: mError, verifying, exportBundle, verifyBundle } = useManifest();
const { isDesktop, openExternal } = useDesktop();
const fileInput = ref<HTMLInputElement | null>(null);
let active = true;
// 切换选中的 workflow 时清掉上次导出/核对残留的瞬态错误横幅(report 按 [H8] 保留跨导航) [审查]
function pick(id: number) { mError.value = null; select(id); }
onMounted(async () => {
  mError.value = null;                    // 进入/重挂载视图时同样重置瞬态错误
  const pw = pendingWorkflowId.value;
  pendingWorkflowId.value = null;
  await load();
  if (!active) return;
  const target = pw != null && workflows.value.some((w) => w.id === pw) ? pw : workflows.value[0]?.id;
  if (target != null) select(target);
});
onUnmounted(() => { active = false; });
function goModel(id: number) { pendingModelId.value = id; view.value = "library"; }
const hit = computed(() => selected.value?.edges.filter((e: any) => e.status === "path" || e.status === "basename").length ?? 0);
const ambiguous = computed(() => selected.value?.edges.filter((e: any) => e.status === "ambiguous").length ?? 0);
const miss = computed(() => selected.value?.edges.filter((e: any) => e.status === "missing").length ?? 0);
const STATUS_RANK: Record<string, number> = { missing: 0, ambiguous: 1, basename: 2, path: 3 };
const sortedEdges = computed(() =>
  [...(selected.value?.edges ?? [])].sort((a: any, b: any) =>
    (STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9)));
function doExport() {
  if (!selected.value) return;
  const stem = selected.value.filename.replace(/\.json$/i, "");
  exportBundle(selected.value.id, `${stem}.combuddy.zip`);
}
async function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) await verifyBundle(f);
  (e.target as HTMLInputElement).value = "";   // 允许连续选同一文件
}
// 跳详情时不清 report:模块级单例的全部意义就是切回来报告还在 [H8]。
// 原文件已有的 goModel(id) 直接复用。
</script>
<template>
  <div>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <div v-if="mError" class="text-orange-400 text-sm mb-3">{{ t("manifest.err_" + mError) }}</div>
    <div v-if="report" class="mb-4 p-3 rounded bg-surface-card">
      <div class="flex items-center justify-between mb-2">
        <div class="text-color font-semibold">{{ t("manifest.reportTitle", { name: report.workflow?.filename ?? "" }) }}</div>
        <button @click="report = null" class="text-color-secondary text-xs hover:underline">{{ t("manifest.close") }}</button>
      </div>
      <div class="text-color-secondary text-xs mb-3">{{ t("manifest.summary", {
        exact: report.summary.present_exact, unverified: report.summary.present_unverified,
        mismatch: report.summary.mismatch, ambiguous: report.summary.ambiguous,
        missing: report.summary.missing }) }}</div>
      <div v-if="!report.summary.total" class="text-color-secondary text-sm">{{ t("manifest.empty") }}</div>

      <div v-for="(it, i) in report.present" :key="'p' + i + it.ref_string" class="flex items-center gap-2 text-sm py-1">
        <span :class="['text-[11px] px-1.5 py-0.5 rounded shrink-0',
          it.confidence === 'exact' ? 'bg-primary/15 text-primary' : 'bg-yellow-500/15 text-yellow-500']">
          {{ t("manifest.cf_" + it.confidence) }}</span>
        <span class="text-color truncate flex-1">{{ it.ref_string }}</span>
        <span v-if="it.needs_hash" class="text-color-secondary text-xs shrink-0" :title="t('manifest.needsHash')">⚠</span>
        <span @click="goModel(it.model_id)" class="text-primary text-xs shrink-0 cursor-pointer hover:underline">{{ t("workflow.viewModel") }}</span>
      </div>

      <div v-for="(it, i) in report.mismatch" :key="'x' + i + it.ref_string" class="flex items-center gap-2 text-sm py-1">
        <span class="text-[11px] px-1.5 py-0.5 rounded shrink-0 bg-orange-400/15 text-orange-400">{{ t("manifest.g_mismatch") }}</span>
        <span class="text-color truncate flex-1">{{ it.ref_string }}</span>
        <a v-if="it.civitai_url" :href="it.civitai_url" target="_blank"
          @click="isDesktop && ($event.preventDefault(), openExternal(it.civitai_url))"
          class="text-primary text-xs shrink-0">{{ t("manifest.openCivitai") }}</a>
        <span @click="goModel(it.model_id)" class="text-primary text-xs shrink-0 cursor-pointer hover:underline">{{ t("workflow.viewModel") }}</span>
      </div>

      <div v-for="(it, i) in report.ambiguous" :key="'a' + i + it.ref_string" class="text-sm py-1">
        <div class="flex items-center gap-2">
          <span class="text-[11px] px-1.5 py-0.5 rounded shrink-0 bg-yellow-500/15 text-yellow-500">{{ t("manifest.g_ambiguous") }}</span>
          <span class="text-color truncate flex-1">{{ it.ref_string }}</span>
          <span class="text-color-secondary text-xs shrink-0">{{ t("manifest.candidates", { n: it.candidates.length }) }}</span>
        </div>
        <div v-for="cd in it.candidates" :key="cd.model_id" @click="goModel(cd.model_id)"
          class="text-color-secondary text-xs pl-6 cursor-pointer hover:text-primary truncate">· {{ cd.rel_path }}</div>
      </div>

      <div v-for="(it, i) in report.missing" :key="'m' + i + it.ref_string" class="flex items-center gap-2 text-sm py-1">
        <span class="text-[11px] px-1.5 py-0.5 rounded shrink-0 bg-orange-400/15 text-orange-400">{{ t("manifest.g_missing") }}</span>
        <span class="text-color truncate flex-1">{{ it.ref_string }}</span>
        <a v-if="it.civitai_url" :href="it.civitai_url" target="_blank"
          @click="isDesktop && ($event.preventDefault(), openExternal(it.civitai_url))"
          class="text-primary text-xs shrink-0">{{ t("manifest.openCivitai") }}</a>
      </div>
    </div>
    <div class="flex gap-4">
      <div class="w-56 shrink-0">
        <div class="flex items-center justify-between mb-4">
          <h1 class="text-xl font-semibold">{{ t("workflow.title") }}</h1>
          <button @click="fileInput?.click()" :disabled="verifying"
            class="text-primary text-xs hover:underline disabled:opacity-50">
            {{ verifying ? t("manifest.verifying") : t("manifest.import") }}
          </button>
          <input ref="fileInput" type="file" accept=".zip" class="hidden" @change="onFile" />
        </div>
        <div v-for="w in workflows" :key="w.id" @click="pick(w.id)"
          :class="['px-3 py-2 rounded text-sm cursor-pointer mb-1',
            selected?.id===w.id ? 'bg-surface-hover text-primary' : 'bg-surface-card text-color-secondary']">
          <div class="truncate">{{ w.filename }}</div>
          <div class="text-[10px] text-color-secondary">{{ t("workflow.hitMiss", { hit: w.resolved, miss: w.missing }) }}<template v-if="w.ambiguous"> · {{ t("workflow.amb", { n: w.ambiguous }) }}</template></div>
        </div>
      </div>
      <div v-if="selected" class="flex-1">
        <div class="flex items-center justify-between mb-3">
          <div class="text-color-secondary text-sm">{{ t("workflow.summary", { hit, ambiguous, miss }) }}</div>
          <button @click="doExport" :disabled="!!selected.parse_error"
            :title="selected.parse_error ? t('manifest.noExport') : t('manifest.exportHint')"
            class="text-primary text-xs hover:underline disabled:opacity-50 disabled:no-underline">
            {{ t("manifest.export") }}
          </button>
        </div>
        <div v-for="(e, i) in sortedEdges" :key="e.ref_string + '|' + e.node_type + '|' + i" class="flex items-center gap-2 text-sm py-1">
          <span :class="['text-[11px] px-1.5 py-0.5 rounded shrink-0',
              e.status==='missing' ? 'bg-orange-400/15 text-orange-400'
              : e.status==='ambiguous' ? 'bg-yellow-500/15 text-yellow-500'
              : e.status==='basename' ? 'bg-surface-hover text-color-secondary'
              : 'bg-primary/15 text-primary']">{{ t("workflow.st_" + e.status) }}</span>
          <span class="text-color truncate flex-1">{{ e.ref_string }}</span>
          <span v-if="e.status==='basename' && e.model_filename" class="text-color-secondary text-xs truncate max-w-48" :title="e.model_filename">→ {{ e.model_filename }}</span>
          <span v-if="e.model_id != null" @click="goModel(e.model_id)" class="text-primary text-xs shrink-0 cursor-pointer hover:underline">{{ t("workflow.viewModel") }}</span>
          <span class="text-color-secondary text-xs shrink-0">{{ e.node_type }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
