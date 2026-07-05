<script setup lang="ts">
import { computed } from "vue";
import { humanSize } from "../format";
const props = defineProps<{ byType: any[] }>();
const max = computed(() => Math.max(1, ...props.byType.map((t) => t.size)));
</script>
<template>
  <div class="bg-[#1e1e24] rounded-xl p-4">
    <div class="text-sm font-semibold text-[#e8e8ea] mb-3">按类型占用</div>
    <div v-for="t in byType" :key="t.dir_type" class="flex items-center gap-3 mb-2">
      <div class="w-40 text-xs text-[#c8c8ce] truncate">{{ t.dir_type }}</div>
      <div class="flex-1 h-2.5 bg-[#2a2a31] rounded-full overflow-hidden">
        <div class="h-full bg-[#2ea043]" :style="{ width: (100*t.size/max) + '%' }"></div>
      </div>
      <div class="w-20 text-right text-xs text-[#8a8a93]">{{ humanSize(t.size) }}</div>
    </div>
  </div>
</template>
