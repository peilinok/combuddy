<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useDetect } from "../useDetect";
const { t } = useI18n();
const emit = defineEmits<{ (e: "done"): void }>();
const { candidates, skipped, loading, error, selected, toggle, confirm } = useDetect();
async function go() { if (await confirm()) emit("done"); }
</script>
<template>
  <div>
    <div v-if="loading" class="text-color-secondary text-sm">{{ t("detect.scanning") }}</div>
    <div v-else-if="error" class="text-red-400 text-sm">
      {{ error === "duplicate" ? t("settings.dupRoot") : error === "not_a_directory" ? t("settings.badRoot") : error }}
    </div>
    <template v-else>
      <label v-for="c in candidates" :key="c.path"
        class="flex items-center gap-2 py-1 text-sm cursor-pointer">
        <input type="checkbox" :checked="selected.has(c.path)" @change="toggle(c.path)" />
        <span class="text-color">{{ c.label }}</span>
        <span class="text-color-secondary text-xs">{{ c.path }}</span>
        <span v-if="c.kind === 'model'" class="text-color-secondary text-xs">·
          {{ c.model_count === null ? t("detect.some") : c.model_count + (c.count_capped ? "+" : "") }}</span>
      </label>
      <div v-if="skipped > 0" class="text-color-secondary text-xs mt-2">{{ t("detect.skipped", { n: skipped }) }}</div>
      <button @click="go" :disabled="selected.size === 0"
        class="mt-3 px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-50">
        {{ t("detect.useSelected") }}</button>
    </template>
  </div>
</template>
