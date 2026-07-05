<script setup lang="ts">
import { ref } from "vue";
import { setRoots, postScan } from "../api";
const emit = defineEmits<{ (e: "done"): void }>();
const modelPath = ref(""); const workflowPath = ref("");
async function save() {
  const roots = [];
  if (modelPath.value) roots.push({ kind: "model", path: modelPath.value, source: "manual" });
  if (workflowPath.value) roots.push({ kind: "workflow", path: workflowPath.value, source: "manual" });
  if (roots.length) {
    await setRoots(roots);
    try { await postScan(); } catch (e) { /* scan-start failure must not block */ }
    emit("done");
  }
}
</script>
<template>
  <div class="max-w-lg mx-auto mt-20 bg-surface-card rounded-xl p-6">
    <div class="text-lg font-semibold text-color mb-4">指认你的目录</div>
    <label class="block text-xs text-color-secondary mb-1">模型目录(如 …/ComfyUI-Shared/models)</label>
    <input v-model="modelPath" class="w-full mb-4 px-3 py-2 rounded bg-surface-hover text-color text-sm" />
    <label class="block text-xs text-color-secondary mb-1">workflow 目录(如 …/user/default/workflows)</label>
    <input v-model="workflowPath" class="w-full mb-4 px-3 py-2 rounded bg-surface-hover text-color text-sm" />
    <button @click="save" class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold">保存并扫描</button>
  </div>
</template>
