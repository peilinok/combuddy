<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useLocate } from "../useLocate";
import { useDesktop } from "../useDesktop";
import { useScanStatus } from "../useScanStatus";
import { useDemo } from "../useDemo";
import { postScan } from "../api";
import { humanSize } from "../format";   // 候选文件大小复用既有 helper(吃 bytes,size_kb 需 ×1024) [H1]
const { t } = useI18n();
const { open, loading, mode, result, error, query, search, searchUnfiltered,
        fallbackToName, siteSearchUrl, expectedPath, target, close } = useLocate();
const { isDesktop, openExternal } = useDesktop();
const { scanning } = useScanStatus();
const { demo } = useDemo();

const path = computed(() => (target.value ? expectedPath(target.value) : ""));
const candidates = computed(() => (mode.value === "name" ? result.value?.candidates ?? [] : []));
const hashFound = computed(() => mode.value === "hash" && result.value?.found === true);
const hashMiss = computed(() => mode.value === "hash" && result.value?.found === false);
const isCivitai = (u: string) => { try { const x = new URL(u); return x.protocol === "https:" && x.hostname === "civitai.com"; } catch { return false; } };
function extern(e: Event, u: string) { if (isDesktop.value) { e.preventDefault(); openExternal(u); } }
async function copyPath() {
  try { await navigator.clipboard.writeText(path.value); }
  catch { /* 桌面 WKWebView 常拒 clipboard,降级提示手动复制 [M10] */ alert(t("locate.copyFailed")); }
}
async function rescan() {
  if (!scanning.value && !demo.value) {
    try { await postScan(); } catch { /* scan-start failure must not block */ }
  }
}
</script>

<template>
  <Dialog v-model:visible="open" modal :header="t('locate.title')" :style="{ width: '32rem' }" @hide="close">
    <!-- 期望路径 -->
    <div class="mb-3">
      <div class="text-color-secondary text-xs mb-1">{{ t("locate.expectedPath") }}</div>
      <div class="flex items-center gap-2">
        <code class="flex-1 text-xs bg-surface-hover rounded px-2 py-1 break-all select-all">{{ path }}</code>
        <button @click="copyPath" class="text-primary text-xs hover:underline shrink-0">{{ t("locate.copy") }}</button>
      </div>
      <div v-if="!target?.dir_type" class="text-color-secondary text-[11px] mt-1">{{ t("locate.dirHint") }}</div>
    </div>

    <!-- 搜索框(name 相关;hash 命中 404 或 429/502 错误态也放开,让用户改用名称搜索 [H2]) -->
    <div v-if="mode !== 'hash' || hashMiss || (mode === 'hash' && error)" class="flex items-center gap-2 mb-3">
      <input v-model="query" @keyup.enter="search"
        class="flex-1 text-sm bg-surface-hover rounded px-2 py-1 outline-none"
        :placeholder="t('locate.searchPlaceholder')" />
      <button @click="search" :disabled="loading || !query"
        class="text-primary text-xs hover:underline disabled:opacity-50 shrink-0">
        {{ loading ? t("locate.searching") : t("locate.search") }}</button>
    </div>

    <div v-if="error" class="text-orange-400 text-sm mb-2">{{ t("locate.err_" + error) }}</div>
    <div v-if="hashMiss" class="text-color-secondary text-sm mb-2">
      {{ t("locate.hashNotFound") }}
      <button @click="fallbackToName" class="text-primary hover:underline ml-1">{{ t("locate.toNameSearch") }}</button>
    </div>

    <!-- hash 命中的单候选 -->
    <div v-if="hashFound" class="text-sm py-1 flex items-center gap-2">
      <span class="text-[11px] px-1.5 py-0.5 rounded bg-primary/15 text-primary shrink-0">{{ result.candidate.model_type }}</span>
      <span class="text-color truncate flex-1">{{ result.candidate.model_name }} · {{ result.candidate.version_name }}</span>
      <a v-if="isCivitai(result.candidate.civitai_url)" :href="result.candidate.civitai_url" target="_blank"
        @click="extern($event, result.candidate.civitai_url)" class="text-primary text-xs shrink-0">{{ t("locate.openCivitai") }}</a>
    </div>

    <!-- name 候选列表:主行 + 文件名/大小副行(成功标准 1 要求展示主模型文件名与大小 [H1]) -->
    <div v-for="(c, i) in candidates" :key="i" class="text-sm py-1">
      <div class="flex items-center gap-2">
        <span v-if="c.file_match" class="text-[11px] px-1.5 py-0.5 rounded bg-primary/15 text-primary shrink-0">{{ t("locate.fileMatch") }}</span>
        <span class="text-color truncate flex-1">{{ c.model_name }} · {{ c.version_name }}
          <span class="text-color-secondary">({{ c.model_type }}, {{ c.base_model }})</span></span>
        <a v-if="isCivitai(c.civitai_url)" :href="c.civitai_url" target="_blank"
          @click="extern($event, c.civitai_url)" class="text-primary text-xs shrink-0">{{ t("locate.openCivitai") }}</a>
      </div>
      <div v-if="c.file?.name" class="text-color-secondary text-[11px] pl-1 truncate">
        {{ c.file.name }}<span v-if="c.file.size_kb"> · {{ humanSize(c.file.size_kb * 1024) }}</span></div>
    </div>

    <!-- 空态 + 逃生门 -->
    <div v-if="mode === 'name' && !loading && result && candidates.length === 0" class="text-color-secondary text-sm py-2">
      {{ t("locate.emptyName") }}
      <div class="text-[11px] mt-1">{{ t("locate.emptyHint") }}</div>
    </div>
    <div v-if="mode === 'name' && result && candidates.length" class="mt-1">
      <button @click="searchUnfiltered" class="text-color-secondary text-xs hover:text-primary">{{ t("locate.searchUnfiltered") }}</button>
    </div>

    <template #footer>
      <a :href="siteSearchUrl()" target="_blank" @click="extern($event, siteSearchUrl())"
        class="text-color-secondary text-xs hover:text-primary mr-auto">{{ t("locate.siteSearch") }}</a>
      <button @click="rescan" :disabled="scanning || demo"
        class="text-primary text-xs hover:underline disabled:opacity-50">
        {{ scanning ? t("locate.rescanning") : t("locate.rescan") }}</button>
    </template>
  </Dialog>
</template>
