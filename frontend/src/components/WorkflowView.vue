<script setup lang="ts">
import { onMounted, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useWorkflows } from "../useWorkflows";
const { t } = useI18n();
const { workflows, selected, load, select, error } = useWorkflows();
onMounted(async () => { await load(); if (workflows.value[0]) select(workflows.value[0].id); });
const hit = computed(() => selected.value?.edges.filter((e: any) => e.status === "path" || e.status === "basename").length ?? 0);
const ambiguous = computed(() => selected.value?.edges.filter((e: any) => e.status === "ambiguous").length ?? 0);
const miss = computed(() => selected.value?.edges.filter((e: any) => e.status === "missing").length ?? 0);
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
        <div v-for="(e, i) in selected.edges" :key="e.ref_string + '|' + e.node_type + '|' + i" class="flex items-center gap-2 text-sm py-1">
          <span :class="e.status==='missing' ? 'text-orange-400' : e.status==='ambiguous' ? 'text-yellow-500' : 'text-primary'">●</span>
          <span class="text-color truncate flex-1">{{ e.ref_string }}</span>
          <span class="text-color-secondary text-xs">{{ e.node_type }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
