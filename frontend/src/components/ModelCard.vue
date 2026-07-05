<script setup lang="ts">
import { humanSize } from "../format";
defineProps<{ m: any; blur: boolean }>();
defineEmits<{ (e: "zoom"): void; (e: "open"): void }>();
</script>
<template>
  <div class="bg-surface-card border border-surface-border rounded-lg p-3 cursor-pointer hover:bg-surface-hover" @click="$emit('open')">
    <div class="aspect-square rounded bg-surface-hover mb-2 overflow-hidden flex items-center justify-center">
      <img v-if="m.has_preview" :src="'/api/preview/' + m.sha256"
        :class="['w-full h-full object-cover', blur ? 'blur-md' : '']" @click.stop="$emit('zoom')" />
      <i v-else class="pi pi-box text-3xl text-color-secondary"></i>
    </div>
    <div class="text-sm text-color truncate">{{ m.civitai_name || m.display_name || m.filename }}</div>
    <div class="flex items-center gap-1 mt-1 flex-wrap">
      <Tag :value="m.dir_type" severity="secondary" />
      <Tag v-if="m.civitai_base || m.label !== '未识别'" :value="m.civitai_base || m.label" />
    </div>
    <div class="text-xs text-color-secondary mt-1">{{ humanSize(m.size) }} · 引用 {{ m.ref_count }}</div>
  </div>
</template>
