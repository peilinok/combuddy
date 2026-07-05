<script setup lang="ts">
import { onMounted } from "vue";
import { useSettings } from "../useSettings";
import ThemePicker from "./ThemePicker.vue";
const { settings, roots, error, load, save, addRoot } = useSettings();
onMounted(load);
</script>
<template>
  <div class="max-w-2xl">
    <h1 class="text-xl font-semibold mb-4">设置</h1>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <Panel header="外观" class="mb-4"><ThemePicker /></Panel>
    <!-- 扫描哈希 / Civitai / 根目录 分区在 Task 6、7 加入 -->
  </div>
</template>
