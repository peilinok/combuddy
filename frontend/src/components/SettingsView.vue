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
    <Panel header="扫描 & 哈希" class="mb-4">
      <div class="flex items-center justify-between mb-3">
        <span>扫描后自动计算 sha256</span>
        <InputSwitch :modelValue="settings.auto_hash" @update:modelValue="save({ auto_hash: $event })" />
      </div>
      <div class="mb-3"><div class="flex justify-between text-sm mb-1"><span>哈希并发</span><span class="text-color-secondary">{{ settings.hash_workers }}</span></div>
        <Slider :modelValue="settings.hash_workers" :min="1" :max="8" @change="save({ hash_workers: $event.value })" /></div>
      <div class="flex items-center justify-between"><span>限速 MB/s(0=不限)</span>
        <InputNumber :modelValue="settings.hash_max_mbps" :min="0" showButtons
          @update:modelValue="save({ hash_max_mbps: $event ?? 0 })" inputClass="w-20" /></div>
    </Panel>
    <Panel header="Civitai 富化" class="mb-4">
      <div class="flex items-center justify-between mb-3">
        <span>扫描后自动联网识别(仅发送哈希)</span>
        <InputSwitch :modelValue="settings.online_enrich" @update:modelValue="save({ online_enrich: $event })" /></div>
      <div><div class="flex justify-between text-sm mb-1"><span>NSFW 模糊阈值(越高越少模糊)</span><span class="text-color-secondary">{{ settings.nsfw_blur_threshold }}</span></div>
        <Slider :modelValue="settings.nsfw_blur_threshold" :min="0" :max="32" @change="save({ nsfw_blur_threshold: $event.value })" /></div>
    </Panel>
    <!-- 根目录 分区在 Task 7 加入 -->
  </div>
</template>
