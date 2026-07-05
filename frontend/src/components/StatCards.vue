<script setup lang="ts">
import { humanSize } from "../format";
const props = defineProps<{ stats: any }>();
</script>
<template>
  <div class="grid grid-cols-4 gap-3">
    <div class="bg-[#202027] rounded-xl p-4">
      <div class="text-xs text-[#8a8a93]">模型总数</div>
      <div class="text-2xl font-bold text-[#e8e8ea]">{{ stats.model_count }}</div>
      <div class="text-xs text-[#8a8a93]">{{ humanSize(stats.total_size) }}</div>
    </div>
    <div class="bg-[#202027] rounded-xl p-4">
      <div class="text-xs text-[#8a8a93]">工作流</div>
      <div class="text-2xl font-bold text-[#e8e8ea]">{{ stats.workflow_count }}</div>
    </div>
    <div class="bg-[#202027] rounded-xl p-4">
      <div class="text-xs text-[#8a8a93]">base 覆盖</div>
      <div class="text-2xl font-bold text-[#e8e8ea]">
        {{ stats.base_coverage.total ? Math.round(100*stats.base_coverage.done/stats.base_coverage.total) : 0 }}%
      </div>
      <div class="text-xs text-[#8a8a93]">读头 {{ stats.base_coverage.done }}/{{ stats.base_coverage.total }}</div>
    </div>
    <div class="bg-[#202027] rounded-xl p-4">
      <div class="text-xs text-[#8a8a93]">未被引用</div>
      <div class="text-2xl font-bold text-[#f0883e]">{{ stats.unreferenced_count }}</div>
      <div class="text-xs text-[#8a8a93]">可清理候选</div>
    </div>
  </div>
</template>
