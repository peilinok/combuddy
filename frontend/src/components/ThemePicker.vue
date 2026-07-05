<script setup lang="ts">
import { useTheme, PALETTES, MODES } from "../useTheme";
const { palette, mode } = useTheme();
const SWATCH: Record<string, string> = { green: "#22c55e", blue: "#3b82f6", cyan: "#06b6d4", purple: "#a855f7", amber: "#f59e0b" };
const MODE_LABEL: Record<string, string> = { auto: "跟随系统", light: "亮", dark: "暗" };
</script>
<template>
  <div>
    <div class="text-sm text-color-secondary mb-2">配色</div>
    <div class="flex gap-2 mb-4">
      <button v-for="p in PALETTES" :key="p" @click="palette = p"
        :title="p" :style="{ background: SWATCH[p] }"
        :class="['w-7 h-7 rounded-full border-2', palette === p ? 'border-color' : 'border-transparent']"></button>
    </div>
    <div class="text-sm text-color-secondary mb-2">明暗</div>
    <div class="flex gap-2">
      <button v-for="m in MODES" :key="m" @click="mode = m"
        :class="['px-3 py-1.5 rounded text-sm', mode === m ? 'bg-primary text-white' : 'bg-surface-hover text-color-secondary']">
        {{ MODE_LABEL[m] }}</button>
    </div>
  </div>
</template>
