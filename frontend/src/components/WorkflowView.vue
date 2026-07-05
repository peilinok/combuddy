<script setup lang="ts">
import { onMounted, computed } from "vue";
import { useWorkflows } from "../useWorkflows";
const { workflows, selected, load, select, error } = useWorkflows();
onMounted(async () => { await load(); if (workflows.value[0]) select(workflows.value[0].id); });
const hit = computed(() => selected.value?.edges.filter((e: any) => e.status === "path" || e.status === "basename").length ?? 0);
const ambiguous = computed(() => selected.value?.edges.filter((e: any) => e.status === "ambiguous").length ?? 0);
const miss = computed(() => selected.value?.edges.filter((e: any) => e.status === "missing").length ?? 0);
</script>
<template>
  <div>
    <div v-if="error" class="text-[#f0883e] text-sm mb-3">{{ error }}</div>
    <div class="flex gap-4">
      <div class="w-56 shrink-0">
        <h1 class="text-xl font-semibold mb-4">Workflow 对应</h1>
        <div v-for="w in workflows" :key="w.id" @click="select(w.id)"
          :class="['px-3 py-2 rounded text-sm cursor-pointer mb-1',
            selected?.id===w.id ? 'bg-[#1b3d29] text-[#4ade80]' : 'bg-[#1e1e24] text-[#c8c8ce]']">
          <div class="truncate">{{ w.filename }}</div>
          <div class="text-[10px] text-[#8a8a93]">命中 {{ w.resolved }} · 缺失 {{ w.missing }}</div>
        </div>
      </div>
      <div v-if="selected" class="flex-1">
        <div class="text-[#8a8a93] text-sm mb-3">命中 {{ hit }} · 歧义 {{ ambiguous }} · 缺失 {{ miss }}</div>
        <div v-for="(e, i) in selected.edges" :key="e.ref_string + '|' + e.node_type + '|' + i" class="flex items-center gap-2 text-sm py-1">
          <span :class="e.status==='missing' ? 'text-[#f0883e]' : e.status==='ambiguous' ? 'text-[#eab308]' : 'text-[#4ade80]'">●</span>
          <span class="text-[#d8d8de] truncate flex-1">{{ e.ref_string }}</span>
          <span class="text-[#6c6c74] text-xs">{{ e.node_type }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
