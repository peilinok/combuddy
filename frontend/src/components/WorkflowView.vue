<script setup lang="ts">
import { onMounted, onUnmounted, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useWorkflows } from "../useWorkflows";
import { view, pendingWorkflowId, pendingModelId } from "../useNav";
const { t } = useI18n();
const { workflows, selected, load, select, error } = useWorkflows();
let active = true;
onMounted(async () => {
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
</script>
<template>
  <div>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <div class="flex gap-4">
      <div class="w-56 shrink-0">
        <h1 class="text-xl font-semibold mb-4">{{ t("workflow.title") }}</h1>
        <div v-for="w in workflows" :key="w.id" @click="select(w.id)"
          :class="['px-3 py-2 rounded text-sm cursor-pointer mb-1',
            selected?.id===w.id ? 'bg-surface-hover text-primary' : 'bg-surface-card text-color-secondary']">
          <div class="truncate">{{ w.filename }}</div>
          <div class="text-[10px] text-color-secondary">{{ t("workflow.hitMiss", { hit: w.resolved, miss: w.missing }) }}<template v-if="w.ambiguous"> · {{ t("workflow.amb", { n: w.ambiguous }) }}</template></div>
        </div>
      </div>
      <div v-if="selected" class="flex-1">
        <div class="text-color-secondary text-sm mb-3">{{ t("workflow.summary", { hit, ambiguous, miss }) }}</div>
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
