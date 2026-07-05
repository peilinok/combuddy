<script setup lang="ts">
import { onMounted, computed } from "vue";
import { useCleanup } from "../useCleanup";
import { humanSize } from "../format";
const { items, selectedIds, selectedBytes, toggle, load, trashSelected, error } = useCleanup();
onMounted(load);
const total = computed(() => items.value.reduce((s, m) => s + m.size, 0));
</script>
<template>
  <div>
    <h1 class="text-xl font-semibold mb-4">清理中心</h1>
    <div v-if="error" class="text-[#f0883e] text-sm mb-3">{{ error }}</div>
    <div class="flex justify-between items-center bg-[#1e1e24] rounded-lg p-4 mb-4">
      <div><div class="font-semibold">未被引用的模型</div>
        <div class="text-xs text-[#8a8a93]">{{ items.length }} 个 · 没有任何 workflow 使用它们</div></div>
      <div class="text-right"><div class="text-[#f0883e] text-xl font-bold">{{ humanSize(total) }}</div>
        <div class="text-[10px] text-[#8a8a93]">可回收</div></div>
    </div>
    <table class="w-full text-sm">
      <tbody>
        <tr v-for="m in items" :key="m.id" class="hover:bg-[#20232a]">
          <td class="py-1.5 w-6"><input type="checkbox" :checked="selectedIds.has(m.id)" @change="toggle(m.id)" /></td>
          <td class="text-[#d8d8de]">{{ m.filename }}</td>
          <td class="text-[#c8c8ce]">{{ m.dir_type }}</td>
          <td class="text-right text-[#c8c8ce]">{{ humanSize(m.size) }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="selectedIds.size" class="flex justify-between items-center bg-[#20232a] rounded-lg p-3 mt-4">
      <span class="text-sm text-[#c8c8ce]">已选 {{ selectedIds.size }} 项 · {{ humanSize(selectedBytes) }} · 均 0 引用,可安全移除</span>
      <button @click="trashSelected" class="px-4 py-1.5 rounded bg-[#2ea043] text-white text-sm font-semibold">移至回收站</button>
    </div>
  </div>
</template>
