<script setup lang="ts">
import { onMounted } from "vue";
import { useLibrary } from "../useLibrary";
import { humanSize } from "../format";
const { models, selected, search, flag, revealed, load, openDetail, error, shouldBlur, reveal } = useLibrary();
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
            <td class="py-1.5 text-[#d8d8de]">
              <span class="inline-flex items-center gap-2">
                <img v-if="m.has_preview" :src="'/api/preview/' + m.sha256"
                  :class="['w-7 h-7 rounded object-cover', shouldBlur(m.nsfw_level) && !revealed.has(m.id) ? 'blur-sm' : '']"
                  @click.stop="reveal(m.id)" />
                {{ m.civitai_name || m.display_name || m.filename }}
              </span>
            </td>
            <td class="text-[#c8c8ce]">{{ m.dir_type }}</td>
            <td :class="m.civitai_found || m.label!=='未识别' ? 'text-[#4ade80]' : 'text-[#6c6c74]'">{{ m.civitai_base || m.label }}</td>
            <td class="text-right text-[#c8c8ce]">{{ humanSize(m.size) }}</td>
            <td :class="['text-right', m.ref_count ? 'text-[#8a8a93]' : 'text-[#f0883e] font-semibold']">{{ m.ref_count }}</td>
          </tr>
          <tr v-if="selected && selected.id === m.id">
            <td colspan="5" class="bg-[#202027] rounded p-3 text-xs">
              <div class="text-[#8a8a93] mb-1">{{ m.dir_type }} · {{ m.label }} · {{ m.precision || '—' }} · {{ humanSize(m.size) }}</div>
              <div class="text-[#6c6c74] font-mono text-[11px] break-all">
                sha256 {{ selected.sha256 || '未计算' }}
              </div>
              <div v-if="selected.civitai_found" class="mt-2 border-t border-[#2a2a30] pt-2">
                <div class="flex gap-3">
                  <img v-if="selected.has_preview" :src="'/api/preview/' + selected.sha256"
                    :class="['w-24 h-24 rounded object-cover shrink-0', shouldBlur(selected.nsfw_level) && !revealed.has(selected.id) ? 'blur-md' : '']"
                    @click="reveal(selected.id)" />
                  <div>
                    <div class="text-[#d8d8de] font-semibold">{{ selected.civitai_name }}
                      <span class="text-[#8a8a93] font-normal">· {{ selected.civitai_base }} · {{ selected.civitai_type }}</span></div>
                    <div v-if="JSON.parse(selected.trigger_words || '[]').length" class="text-[#c8c8ce] mt-1">
                      触发词:<code v-for="t in JSON.parse(selected.trigger_words)" :key="t" class="mr-1 px-1 bg-[#17171c] rounded">{{ t }}</code></div>
                    <a :href="selected.civitai_url" target="_blank" class="text-[#4ade80] text-[11px]">在 Civitai 查看 ↗</a>
                  </div>
                </div>
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
