<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useLocate } from "../useLocate";
import { useDesktop } from "../useDesktop";
import { useScanStatus } from "../useScanStatus";
import { useDownload } from "../useDownload";
import { useDemo } from "../useDemo";
import { postScan, getRoots } from "../api";
import { humanSize } from "../format";   // 候选文件大小复用既有 helper(吃 bytes,size_kb 需 ×1024) [H1]
const { t } = useI18n();
const { open, loading, mode, result, error, query, search, searchUnfiltered,
        fallbackToName, siteSearchUrl, expectedPath, target, close, fullBase } = useLocate();
const { isDesktop, openExternal } = useDesktop();
const { scanning, stats } = useScanStatus();
const { demo } = useDemo();
const { downloading, progress, downloadError, startDownload } = useDownload();

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

// 下载:候选行(hash 命中的单候选 / name 候选列表)带 c.download 时可下 [Task 9]
const modelRoots = ref<any[]>([]);
const rootChoice = ref<number | null>(null);
onMounted(async () => {
  try { const r = await getRoots(); modelRoots.value = (r.roots ?? []).filter((x: any) => x.kind === "model"); }
  catch { /* 拉取失败:effectiveRootId 保持空,下载按钮自然禁用,不打断既有 locate 流程 */ }
});
watch(target, () => { rootChoice.value = null; });   // 每次重新「帮我找」强制重选,防默默下到不常用盘 [M8]
const effectiveRootId = computed(() => modelRoots.value.length === 1 ? modelRoots.value[0].id : rootChoice.value);
const hasDownloadable = computed(() =>
  (hashFound.value && !!result.value?.candidate?.download) ||
  (mode.value === "name" && candidates.value.some((c: any) => c.download)));
function keyMissing() { return stats.value.civitai_api_key_set === false; }
function isActive(c: any) {
  // 全局单槽位:用 target.ref_string 的基名(而非 Civitai 的 c.download.filename)与 DOWNLOAD_STATUS.filename
  // 比对——后端落盘名来自 ref_string,几乎从不等于 Civitai 文件名,原写法导致进度条几乎不显示 [review Important I-3]
  const s = stats.value.download;
  return !!(c?.download && target.value && s?.running && s?.filename === fullBase(target.value.ref_string));
}
function canDownload(c: any) {
  return !!c?.download && !!target.value?.dir_type && effectiveRootId.value != null
    && !keyMissing() && !downloading.value;   // 预先禁用而非只靠错误码 [M6]
}
function buildSpec(c: any, tgt: any, rootId: number) {
  return { ...c.download, dir_type: tgt.dir_type, ref_string: tgt.ref_string, root_id: rootId };
}
function doDownload(c: any) {
  if (!target.value || !c.download || effectiveRootId.value == null) return;
  startDownload(buildSpec(c, target.value, effectiveRootId.value));
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
    <!-- 下载失败:同步(403/已在下载)+ 后台(sha_mismatch/auth/disk_full 等)合并展示,否则用户看不到任何失败文案 [B2] -->
    <div v-if="downloadError" class="text-orange-400 text-sm mb-2">{{ downloadError === "auth" && !stats.civitai_api_key_set ? t("download.err_authNoKey") : t("download.err_" + downloadError) }}</div>
    <div v-if="hashMiss" class="text-color-secondary text-sm mb-2">
      {{ t("locate.hashNotFound") }}
      <button @click="fallbackToName" class="text-primary hover:underline ml-1">{{ t("locate.toNameSearch") }}</button>
    </div>

    <!-- 下载:多 model root 选择器(单 root 直接用,不显示) + 未配 key 提示 [M8] -->
    <div v-if="hasDownloadable && modelRoots.length > 1" class="mb-2">
      <select v-model="rootChoice" class="w-full text-xs bg-surface-hover rounded px-2 py-1 outline-none">
        <option :value="null" disabled>{{ t("download.selectRoot") }}</option>
        <option v-for="r in modelRoots" :key="r.id" :value="r.id">{{ r.path }}</option>
      </select>
    </div>
    <div v-if="hasDownloadable && keyMissing()" class="text-color-secondary text-[11px] mb-2">{{ t("download.err_authNoKey") }}</div>

    <!-- hash 命中的单候选 -->
    <div v-if="hashFound" class="text-sm py-1">
      <div class="flex items-center gap-2">
        <span class="text-[11px] px-1.5 py-0.5 rounded bg-primary/15 text-primary shrink-0">{{ result.candidate.model_type }}</span>
        <span class="text-color truncate flex-1">{{ result.candidate.model_name }} · {{ result.candidate.version_name }}</span>
        <a v-if="isCivitai(result.candidate.civitai_url)" :href="result.candidate.civitai_url" target="_blank"
          @click="extern($event, result.candidate.civitai_url)" class="text-primary text-xs shrink-0">{{ t("locate.openCivitai") }}</a>
        <button v-if="result.candidate.download && !isActive(result.candidate)" @click="doDownload(result.candidate)"
          :disabled="!canDownload(result.candidate)" :title="keyMissing() ? t('download.err_authNoKey') : ''"
          class="text-primary text-xs shrink-0 hover:underline disabled:opacity-50">{{ t("download.cta") }}</button>
      </div>
      <div v-if="isActive(result.candidate)" class="mt-1 flex items-center gap-2">
        <ProgressBar v-if="stats.download?.total" :value="progress" style="height:.4rem" class="flex-1" />
        <ProgressBar v-else mode="indeterminate" style="height:.4rem" class="flex-1" />
        <span class="text-color-secondary text-[11px] shrink-0">{{ stats.download?.total ? progress + "%" : t("download.downloading") }}</span>
      </div>
    </div>

    <!-- name 候选列表:主行 + 文件名/大小副行(成功标准 1 要求展示主模型文件名与大小 [H1]) -->
    <div v-for="(c, i) in candidates" :key="i" class="text-sm py-1">
      <div class="flex items-center gap-2">
        <span v-if="c.file_match" class="text-[11px] px-1.5 py-0.5 rounded bg-primary/15 text-primary shrink-0">{{ t("locate.fileMatch") }}</span>
        <span class="text-color truncate flex-1">{{ c.model_name }} · {{ c.version_name }}
          <span class="text-color-secondary">({{ c.model_type }}, {{ c.base_model }})</span></span>
        <a v-if="isCivitai(c.civitai_url)" :href="c.civitai_url" target="_blank"
          @click="extern($event, c.civitai_url)" class="text-primary text-xs shrink-0">{{ t("locate.openCivitai") }}</a>
        <button v-if="c.download && !isActive(c)" @click="doDownload(c)"
          :disabled="!canDownload(c)" :title="keyMissing() ? t('download.err_authNoKey') : ''"
          class="text-primary text-xs shrink-0 hover:underline disabled:opacity-50">{{ t("download.cta") }}</button>
      </div>
      <div v-if="c.file?.name" class="text-color-secondary text-[11px] pl-1 truncate">
        {{ c.file.name }}<span v-if="c.file.size_kb"> · {{ humanSize(c.file.size_kb * 1024) }}</span></div>
      <div v-if="isActive(c)" class="mt-1 flex items-center gap-2 pl-1">
        <ProgressBar v-if="stats.download?.total" :value="progress" style="height:.4rem" class="flex-1" />
        <ProgressBar v-else mode="indeterminate" style="height:.4rem" class="flex-1" />
        <span class="text-color-secondary text-[11px] shrink-0">{{ stats.download?.total ? progress + "%" : t("download.downloading") }}</span>
      </div>
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
