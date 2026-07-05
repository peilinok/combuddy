<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useSettings } from "../useSettings";
import { setLocale } from "../i18n";
import ThemePicker from "./ThemePicker.vue";
const { t, locale } = useI18n();
const { settings, roots, error, load, save, addRoot } = useSettings();
const newKind = ref("model");
const newPath = ref("");
onMounted(load);
</script>
<template>
  <div class="max-w-2xl">
    <h1 class="text-xl font-semibold mb-4">{{ t("settings.title") }}</h1>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <Panel :header="t('settings.appearance')" class="mb-4">
      <ThemePicker />
      <div class="text-sm text-color-secondary mb-2 mt-4">{{ t("settings.language") }}</div>
      <div class="flex gap-2">
        <button @click="setLocale('zh')"
          :class="['px-3 py-1.5 rounded text-sm', locale === 'zh' ? 'bg-primary text-white' : 'bg-surface-hover text-color-secondary']">
          {{ t("settings.langZh") }}</button>
        <button @click="setLocale('en')"
          :class="['px-3 py-1.5 rounded text-sm', locale === 'en' ? 'bg-primary text-white' : 'bg-surface-hover text-color-secondary']">
          {{ t("settings.langEn") }}</button>
      </div>
    </Panel>
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
    <Panel header="根目录">
      <div v-for="r in roots" :key="r.path" class="flex justify-between text-sm py-1 border-b border-surface-border last:border-0">
        <span class="text-color truncate">{{ r.path }}</span><Tag :value="r.kind" /></div>
      <div class="flex gap-2 mt-3">
        <select v-model="newKind" class="bg-surface-hover rounded px-2 text-sm"><option value="model">model</option><option value="workflow">workflow</option></select>
        <InputText v-model="newPath" placeholder="目录绝对路径" class="flex-1" />
        <Button label="添加" @click="newPath && addRoot(newKind, newPath).then(() => (newPath = ''))" />
      </div>
    </Panel>
  </div>
</template>
