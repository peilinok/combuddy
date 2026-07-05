<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { useDashboard } from "../useDashboard";
import StatCards from "./StatCards.vue";
import TypePanel from "./TypePanel.vue";
const { stats, scanning, error, startScan, refresh, startPolling, stopPolling } = useDashboard();
onMounted(async () => { await refresh(); startPolling(); });
onUnmounted(stopPolling);
</script>
<template>
  <div>
    <div v-if="error" class="text-[#f0883e] text-sm mb-3">{{ error }}</div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-semibold">Dashboard</h1>
      <button @click="startScan" :disabled="scanning"
        class="px-4 py-2 rounded-lg bg-[#2ea043] text-white text-sm font-semibold disabled:opacity-50">
        {{ scanning ? "扫描中…" : "扫描 / 刷新" }}
      </button>
    </div>
    <StatCards :stats="stats" class="mb-4" />
    <TypePanel :byType="stats.by_type" />
  </div>
</template>
