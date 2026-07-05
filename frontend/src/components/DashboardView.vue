<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { useDashboard } from "../useDashboard";
import StatCards from "./StatCards.vue";
import TypePanel from "./TypePanel.vue";
const { stats, scanning, settings, error, startScan, cancelHash, loadSettings,
  saveSettings, refresh, startPolling, stopPolling } = useDashboard();
onMounted(async () => { await loadSettings(); await refresh(); startPolling(); });
onUnmounted(stopPolling);
</script>
<template>
  <div>
    <div v-if="error" class="text-[#f0883e] text-sm mb-3">{{ error }}</div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-semibold">Dashboard</h1>
      <button @click="startScan" :disabled="scanning"
        class="px-4 py-2 rounded-lg bg-[#2ea043] text-white text-sm font-semibold disabled:opacity-50">
        {{ scanning ? (stats.scan?.phase === 'hashing' ? "计算指纹中…" : "扫描中…") : "扫描 / 刷新" }}
      </button>
    </div>
    <StatCards :stats="stats" class="mb-4" />
    <div class="rounded-lg bg-[#17171c] border border-[#26262e] p-4 mb-4">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold">指纹 (sha256)</span>
        <label class="flex items-center gap-2 text-xs text-[#8a8a93] cursor-pointer">
          <input type="checkbox" :checked="settings.auto_hash"
            @change="saveSettings({ auto_hash: ($event.target as HTMLInputElement).checked })" />
          扫描后自动计算
        </label>
      </div>
      <div class="text-sm text-[#c8c8ce] mb-2">
        {{ stats.hash_coverage?.hashed ?? 0 }} / {{ stats.hash_coverage?.total ?? 0 }} 已计算指纹
      </div>
      <div class="flex items-center gap-4 text-xs text-[#8a8a93]">
        <label class="flex items-center gap-1">并发
          <input type="number" min="1" max="8" :value="settings.hash_workers"
            @change="saveSettings({ hash_workers: +($event.target as HTMLInputElement).value })"
            class="w-14 px-2 py-1 rounded bg-[#202027] text-[#c8c8ce]" /></label>
        <label class="flex items-center gap-1">限速
          <input type="number" min="0" :value="settings.hash_max_mbps"
            @change="saveSettings({ hash_max_mbps: +($event.target as HTMLInputElement).value })"
            class="w-16 px-2 py-1 rounded bg-[#202027] text-[#c8c8ce]" /> MB/s(0=不限)</label>
      </div>
      <div v-if="stats.scan?.phase === 'hashing'" class="mt-3 flex items-center gap-3">
        <progress class="flex-1 h-2" :value="stats.scan.hash_done" :max="stats.scan.hash_total || 1"></progress>
        <span class="text-xs text-[#8a8a93]">{{ stats.scan.hash_done }}/{{ stats.scan.hash_total }}</span>
        <button @click="cancelHash"
          class="px-2 py-1 rounded text-xs bg-[#3d1f1f] text-[#f0883e]">取消</button>
      </div>
    </div>
    <TypePanel :byType="stats.by_type" />
  </div>
</template>
