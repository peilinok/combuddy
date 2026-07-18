<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useSettings } from "../useSettings";
import { useDetect } from "../useDetect";
import { useDesktop } from "../useDesktop";
import { setLocale } from "../i18n";
import ThemePicker from "./ThemePicker.vue";
import DetectPanel from "./DetectPanel.vue";
const { t, locale } = useI18n();
const { settings, roots, error, saveState, addResult, load, save, addRoot, removeRoot, saveApiKey } = useSettings();
const { load: loadDetect } = useDetect();
const { isDesktop, pickFolder } = useDesktop();
const newKind = ref("model");
const newPath = ref("");
const showDetect = ref(false);
const apiKeyInput = ref("");
const editingApiKey = ref(false);
onMounted(load);
async function onSaveApiKey() {
  if (!apiKeyInput.value) return;
  await saveApiKey(apiKeyInput.value);
  if (!error.value) { apiKeyInput.value = ""; editingApiKey.value = false; }
}
async function onClearApiKey() {
  await saveApiKey("");
  if (!error.value) editingApiKey.value = false;
}
async function onRemoveRoot(r: any) {
  if (!window.confirm(t("settings.removeConfirm", { path: r.path }))) return;
  await removeRoot(r.id);
}
async function onAddRoot() {
  if (!newPath.value) return;
  const ok = await addRoot(newKind.value, newPath.value);
  if (ok) newPath.value = "";
}
</script>
<template>
  <div class="max-w-2xl">
    <h1 class="text-xl font-semibold mb-4">{{ t("settings.title") }}
      <span v-if="saveState !== 'idle'" class="text-xs font-normal text-color-secondary ml-2">
        {{ saveState === 'saving' ? t("settings.saving") : t("settings.saved") }}</span></h1>
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
    <Panel :header="t('settings.scanHash')" class="mb-4">
      <div class="flex items-center justify-between mb-3">
        <span>{{ t("settings.autoHash") }}</span>
        <InputSwitch :modelValue="settings.auto_hash" @update:modelValue="save({ auto_hash: $event })" />
      </div>
      <div class="mb-3"><div class="flex justify-between text-sm mb-1"><span>{{ t("settings.hashWorkers") }}</span><span class="text-color-secondary">{{ settings.hash_workers }}</span></div>
        <Slider :modelValue="settings.hash_workers" :min="1" :max="8" @change="save({ hash_workers: $event.value })" /></div>
      <div class="flex items-center justify-between"><span>{{ t("settings.maxMbps") }}</span>
        <InputNumber :modelValue="settings.hash_max_mbps" :min="0" showButtons
          @update:modelValue="save({ hash_max_mbps: $event ?? 0 })" inputClass="w-20" /></div>
    </Panel>
    <Panel :header="t('settings.civitaiEnrich')" class="mb-4">
      <div class="flex items-center justify-between mb-3">
        <span>{{ t("settings.onlineEnrich") }}</span>
        <InputSwitch :modelValue="settings.online_enrich" @update:modelValue="save({ online_enrich: $event })" /></div>
      <div class="mb-3"><div class="flex justify-between text-sm mb-1"><span>{{ t("settings.nsfwThreshold") }}</span><span class="text-color-secondary">{{ settings.nsfw_blur_threshold }}</span></div>
        <Slider :modelValue="settings.nsfw_blur_threshold" :min="0" :max="32" @change="save({ nsfw_blur_threshold: $event.value })" /></div>
      <div class="pt-3 border-t border-surface-border">
        <div class="text-sm mb-1">{{ t("download.keyLabel") }}</div>
        <div class="text-color-secondary text-xs mb-2">{{ t("download.keyHint") }}</div>
        <div v-if="!settings.civitai_api_key_set || editingApiKey" class="flex gap-2">
          <input v-model="apiKeyInput" type="password" :placeholder="t('download.keyLabel')"
            class="flex-1 text-sm bg-surface-hover rounded px-2 py-1 outline-none" />
          <Button :label="t('download.keySave')" :disabled="!apiKeyInput" @click="onSaveApiKey" />
        </div>
        <div v-else class="flex items-center gap-3 text-sm">
          <span class="text-color-secondary">{{ t("download.keyConfigured") }} ✓</span>
          <button @click="editingApiKey = true" class="text-primary text-xs hover:underline">{{ t("download.keyChange") }}</button>
          <button @click="onClearApiKey" class="text-primary text-xs hover:underline">{{ t("download.keyClear") }}</button>
        </div>
      </div>
    </Panel>
    <Panel :header="t('settings.roots')">
      <div v-for="r in roots" :key="r.id ?? r.path" class="flex justify-between items-center text-sm py-1 border-b border-surface-border last:border-0">
        <span class="text-color truncate">{{ r.path }}</span>
        <span class="flex items-center gap-2 shrink-0"><Tag :value="r.kind" />
          <button @click="onRemoveRoot(r)" :title="t('settings.removeRoot')"
            class="text-color-secondary hover:text-orange-400"><i class="pi pi-times text-xs"></i></button></span>
      </div>
      <div class="flex gap-2 mt-3">
        <select v-model="newKind" class="bg-surface-hover rounded px-2 text-sm"><option value="model">model</option><option value="workflow">workflow</option></select>
        <InputText v-model="newPath" :placeholder="t('settings.pathPlaceholder')" class="flex-1" />
        <Button v-if="isDesktop" :label="t('setup.browse')" @click="pickFolder().then(p => p && (newPath = p))" />
        <Button :label="t('settings.add')" :disabled="!newPath" @click="onAddRoot" />
      </div>
      <div v-if="addResult && !addResult.ok" class="text-orange-400 text-xs mt-1">
        {{ t(addResult.reason === "duplicate" ? "settings.dupRoot" : "settings.badRoot") }}
      </div>
      <button @click="showDetect = !showDetect; showDetect && loadDetect()" class="mt-2 text-xs text-primary underline">{{ t("detect.rescan") }}</button>
      <DetectPanel v-if="showDetect" @done="showDetect = false; load()" />
    </Panel>
  </div>
</template>
