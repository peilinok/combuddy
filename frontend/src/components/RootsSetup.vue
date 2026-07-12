<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { setRoots, postScan } from "../api";
import { useDetect } from "../useDetect";
import { useDesktop } from "../useDesktop";
import DetectPanel from "./DetectPanel.vue";
const { t } = useI18n();
const emit = defineEmits<{ (e: "done"): void }>();
const { candidates, loading, load } = useDetect();
const { isDesktop, pickFolder } = useDesktop();
const manual = ref(false);
const modelPath = ref(""); const workflowPath = ref("");
const setupError = ref("");
onMounted(load);
async function browse(target: "model" | "workflow") {
  const p = await pickFolder();
  if (p) (target === "model" ? (modelPath.value = p) : (workflowPath.value = p));
}
async function saveManual() {
  const roots = [];
  if (modelPath.value) roots.push({ kind: "model", path: modelPath.value, source: "manual" });
  if (workflowPath.value) roots.push({ kind: "workflow", path: workflowPath.value, source: "manual" });
  if (roots.length) {
    setupError.value = "";
    try {
      const r = await setRoots(roots);
      if (!r.results?.some((result: any) => result.ok)) {
        setupError.value = t(r.results?.[0]?.reason === "duplicate" ? "settings.dupRoot" : "settings.badRoot");
        return;
      }
      try { await postScan(); } catch { /* scan-start failure must not block */ }
      emit("done");
    } catch (e: any) { setupError.value = String(e?.message ?? e); }
  }
}
</script>
<template>
  <div class="max-w-lg mx-auto mt-20 bg-surface-card rounded-xl p-6">
    <div class="text-lg font-semibold text-color mb-4">{{ t("setup.title") }}</div>
    <div v-if="setupError" class="text-red-400 text-sm mb-3">{{ setupError }}</div>
    <DetectPanel v-if="!manual && (loading || candidates.length)" @done="emit('done')" />
    <template v-if="!loading && !candidates.length || manual">
      <label class="block text-xs text-color-secondary mb-1">{{ t("setup.modelDir") }}</label>
      <div class="flex gap-2 mb-4">
        <input v-model="modelPath" class="flex-1 px-3 py-2 rounded bg-surface-hover text-color text-sm" />
        <button v-if="isDesktop" @click="browse('model')" class="px-3 rounded bg-surface-hover text-color text-sm">{{ t("setup.browse") }}</button>
      </div>
      <label class="block text-xs text-color-secondary mb-1">{{ t("setup.workflowDir") }}</label>
      <div class="flex gap-2 mb-4">
        <input v-model="workflowPath" class="flex-1 px-3 py-2 rounded bg-surface-hover text-color text-sm" />
        <button v-if="isDesktop" @click="browse('workflow')" class="px-3 rounded bg-surface-hover text-color text-sm">{{ t("setup.browse") }}</button>
      </div>
      <button @click="saveManual" class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold">{{ t("setup.saveAndScan") }}</button>
    </template>
    <button v-if="!manual && candidates.length" @click="manual = true" class="block mt-3 text-xs text-color-secondary underline">{{ t("setup.manualInstead") }}</button>
  </div>
</template>
