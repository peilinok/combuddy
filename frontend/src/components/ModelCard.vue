<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { humanSize } from "../format";
import { displayLabel, isIdentified } from "../labels";
const { t } = useI18n();
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
      <Tag v-if="isIdentified(m)" :value="displayLabel(m, t)" />
    </div>
    <div class="text-xs text-color-secondary mt-1">{{ humanSize(m.size) }} · {{ t("card.refCount", { n: m.ref_count }) }}</div>
  </div>
</template>
