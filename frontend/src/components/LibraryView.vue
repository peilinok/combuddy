<script setup lang="ts">
import { onMounted } from "vue";
import { useLibrary } from "../useLibrary";
import { humanSize } from "../format";
const { models, selected, search, flag, load, openDetail, error } = useLibrary();
onMounted(load);
function setFlag(f: string) { flag.value = flag.value === f ? "" : f; load(); }
</script>
<template>
  <div>
    <h1 class="text-xl font-semibold mb-4">模型库</h1>
    <div v-if="error" class="text-[#f0883e] text-sm mb-3">{{ error }}</div>
    <div class="flex gap-2 mb-4">
      <input v-model="search" @input="load" placeholder="搜索名称…"
        class="px-3 py-2 rounded bg-[#202027] text-sm w-64" />
      <button @click="setFlag('unknown')" :class="['px-3 rounded text-xs', flag==='unknown'?'bg-[#1b3d29] text-[#4ade80]':'bg-[#202027] text-[#c8c8ce]']">未识别</button>
      <button @click="setFlag('unreferenced')" :class="['px-3 rounded text-xs', flag==='unreferenced'?'bg-[#1b3d29] text-[#4ade80]':'bg-[#202027] text-[#c8c8ce]']">未被引用</button>
    </div>
    <table class="w-full text-sm">
      <thead class="text-[#8a8a93] text-xs"><tr>
        <th class="text-left font-normal pb-2">名称</th><th class="text-left font-normal">类型</th>
        <th class="text-left font-normal">标识</th><th class="text-right font-normal">大小</th><th class="text-right font-normal">用量</th>
      </tr></thead>
      <tbody>
        <template v-for="m in models" :key="m.id">
          <tr @click="openDetail(m.id)" class="cursor-pointer hover:bg-[#20232a]">
            <td class="py-1.5 text-[#d8d8de]">{{ m.display_name || m.filename }}</td>
            <td class="text-[#c8c8ce]">{{ m.dir_type }}</td>
            <td :class="m.label==='未识别' ? 'text-[#6c6c74]' : 'text-[#4ade80]'">{{ m.label }}</td>
            <td class="text-right text-[#c8c8ce]">{{ humanSize(m.size) }}</td>
            <td :class="['text-right', m.ref_count ? 'text-[#8a8a93]' : 'text-[#f0883e] font-semibold']">{{ m.ref_count }}</td>
          </tr>
          <tr v-if="selected && selected.id === m.id">
            <td colspan="5" class="bg-[#202027] rounded p-3 text-xs">
              <div class="text-[#8a8a93] mb-1">{{ m.dir_type }} · {{ m.label }} · {{ m.precision || '—' }} · {{ humanSize(m.size) }}</div>
              <div class="text-[#6c6c74] font-mono text-[11px] break-all">
                sha256 {{ selected.sha256 || '未计算' }}
              </div>
              <div class="text-[#c8c8ce] font-semibold mt-2">反向依赖 — 被 {{ selected.workflows.length }} 个 workflow 引用</div>
              <div v-for="w in selected.workflows" :key="w.id" class="text-[#c8c8ce]">· {{ w.filename }}</div>
              <div v-if="!selected.workflows.length" class="text-[#f0883e]">没有 workflow 引用它(可清理)</div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>
