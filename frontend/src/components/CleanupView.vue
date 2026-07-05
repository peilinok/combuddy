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
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <div class="flex justify-between items-center bg-surface-card rounded-lg p-4 mb-4">
      <div><div class="font-semibold">未被引用的模型</div>
        <div class="text-xs text-color-secondary">{{ items.length }} 个 · 没有任何 workflow 使用它们</div></div>
      <div class="text-right"><div class="text-orange-400 text-xl font-bold">{{ humanSize(total) }}</div>
        <div class="text-[10px] text-color-secondary">可回收</div></div>
    </div>
    <table class="w-full text-sm">
      <tbody>
        <tr v-for="m in items" :key="m.id" class="hover:bg-surface-hover">
          <td class="py-1.5 w-6"><input type="checkbox" :checked="selectedIds.has(m.id)" @change="toggle(m.id)" /></td>
          <td class="text-color">{{ m.filename }}</td>
          <td class="text-color-secondary">{{ m.dir_type }}</td>
          <td class="text-right text-color-secondary">{{ humanSize(m.size) }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="selectedIds.size" class="flex justify-between items-center bg-surface-hover rounded-lg p-3 mt-4">
      <span class="text-sm text-color-secondary">已选 {{ selectedIds.size }} 项 · {{ humanSize(selectedBytes) }} · 均 0 引用,可安全移除</span>
      <button @click="trashSelected" class="px-4 py-1.5 rounded bg-primary text-white text-sm font-semibold">移至回收站</button>
    </div>
  </div>
</template>
