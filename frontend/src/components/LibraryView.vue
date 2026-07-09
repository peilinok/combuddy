<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { useLibrary } from "../useLibrary";
import { useDesktop } from "../useDesktop";
import { humanSize } from "../format";
import { displayLabel, isIdentified } from "../labels";
import ModelCard from "./ModelCard.vue";
const { t } = useI18n();
const { models, selected, search, flag, layout, revealed, lightbox, load, openDetail, error,
  shouldBlur, reveal, openLightbox, closeLightbox, typeFilter, collapsed, typeCounts, visibleModels } = useLibrary();
const { isDesktop, reveal: revealInFinder, openExternal } = useDesktop();
function onKey(e: KeyboardEvent) { if (e.key === "Escape") closeLightbox(); }
onMounted(() => { load(); window.addEventListener("keydown", onKey); });
onUnmounted(() => window.removeEventListener("keydown", onKey));
function setFlag(f: string) { flag.value = flag.value === f ? "" : f; load(); }
</script>
<template>
  <div>
    <h1 class="text-xl font-semibold mb-4">{{ t("library.title") }}</h1>
    <div v-if="error" class="text-orange-400 text-sm mb-3">{{ error }}</div>
    <div class="flex gap-2 mb-4 items-center">
      <input v-model="search" @input="load" :placeholder="t('library.search')"
        class="px-3 py-2 rounded bg-surface-card text-sm w-64" />
      <button @click="setFlag('unknown')" :class="['px-3 rounded text-xs', flag==='unknown'?'bg-surface-hover text-primary':'bg-surface-card text-color-secondary']">{{ t("library.unknown") }}</button>
      <button @click="setFlag('unreferenced')" :class="['px-3 rounded text-xs', flag==='unreferenced'?'bg-surface-hover text-primary':'bg-surface-card text-color-secondary']">{{ t("library.unreferenced") }}</button>
      <div class="ml-auto flex gap-1">
        <button @click="layout = 'grid'" :title="t('library.gridView')"
          :class="['w-9 h-9 rounded flex items-center justify-center', layout==='grid'?'bg-surface-hover text-primary':'bg-surface-card text-color-secondary']">
          <i class="pi pi-th-large"></i>
        </button>
        <button @click="layout = 'list'" :title="t('library.listView')"
          :class="['w-9 h-9 rounded flex items-center justify-center', layout==='list'?'bg-surface-hover text-primary':'bg-surface-card text-color-secondary']">
          <i class="pi pi-bars"></i>
        </button>
      </div>
    </div>
    <div class="flex gap-4">
      <aside :class="['shrink-0 transition-all', collapsed ? 'w-8' : 'w-48']">
        <button @click="collapsed = !collapsed" class="text-color-secondary text-xs mb-2 flex items-center gap-1">
          <i :class="collapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'"></i><span v-if="!collapsed">{{ t("library.type") }}</span>
        </button>
        <div v-if="!collapsed">
          <button @click="typeFilter = ''" :class="['w-full text-left px-2 py-1 rounded text-sm', typeFilter==='' ? 'bg-surface-hover text-primary' : 'text-color-secondary hover:bg-surface-hover']">{{ t("library.all") }} ({{ models.length }})</button>
          <button v-for="tc in typeCounts" :key="tc.dir_type" @click="typeFilter = tc.dir_type"
            :class="['w-full text-left px-2 py-1 rounded text-sm truncate', typeFilter===tc.dir_type ? 'bg-surface-hover text-primary' : 'text-color-secondary hover:bg-surface-hover']">
            {{ tc.dir_type }} ({{ tc.count }})</button>
        </div>
      </aside>
      <div class="flex-1 min-w-0">
        <DataView :value="visibleModels" :layout="layout">
          <template #grid="{ items }">
            <div class="grid grid-cols-4 gap-3">
              <ModelCard v-for="m in items" :key="m.id" :m="m"
                :blur="shouldBlur(m.nsfw_level) && !revealed.has(m.id)"
                @zoom="openLightbox(m)" @open="openDetail(m.id)" />
            </div>
          </template>
          <template #list="{ items }">
            <table class="w-full text-sm">
              <thead class="text-color-secondary text-xs"><tr>
                <th class="text-left font-normal pb-2">{{ t("library.colName") }}</th><th class="text-left font-normal">{{ t("library.colType") }}</th>
                <th class="text-left font-normal">{{ t("library.colLabel") }}</th><th class="text-right font-normal">{{ t("library.colSize") }}</th><th class="text-right font-normal">{{ t("library.colUsage") }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="m in items" :key="m.id" @click="openDetail(m.id)" class="cursor-pointer hover:bg-surface-hover">
                  <td class="py-1.5 text-color">
                    <span class="inline-flex items-center gap-2">
                      <img v-if="m.has_preview" :src="'/api/preview/' + m.sha256"
                        :class="['w-7 h-7 rounded object-cover cursor-zoom-in', shouldBlur(m.nsfw_level) && !revealed.has(m.id) ? 'blur-sm' : '']"
                        @click.stop="openLightbox(m)" />
                      {{ m.civitai_name || m.display_name || m.filename }}
                    </span>
                  </td>
                  <td class="text-color-secondary">{{ m.dir_type }}</td>
                  <td :class="isIdentified(m) ? 'text-primary' : 'text-color-secondary'">{{ displayLabel(m, t) }}</td>
                  <td class="text-right text-color-secondary">{{ humanSize(m.size) }}</td>
                  <td :class="['text-right', m.ref_count ? 'text-color-secondary' : 'text-orange-400 font-semibold']">{{ m.ref_count }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <template #empty>
            <div class="text-color-secondary text-sm py-6 text-center">{{ t("library.empty") }}</div>
          </template>
        </DataView>
        <div v-if="selected" class="bg-surface-card rounded p-3 text-xs mt-4">
          <div class="text-color-secondary mb-1">{{ selected.dir_type }} · {{ displayLabel(selected, t) }} · {{ selected.precision || '—' }} · {{ humanSize(selected.size) }}</div>
          <button v-if="isDesktop" @click="revealInFinder(selected.path)" class="text-color-secondary text-[11px] underline">{{ t("desktop.revealInFiles") }}</button>
          <div class="text-color-secondary font-mono text-[11px] break-all">
            {{ t("library.sha256") }} {{ selected.sha256 || t("library.notHashed") }}
          </div>
          <div v-if="selected.civitai_found" class="mt-2 border-t border-surface-border pt-2">
            <div class="flex gap-3">
              <img v-if="selected.has_preview" :src="'/api/preview/' + selected.sha256"
                :class="['w-24 h-24 rounded object-cover shrink-0 cursor-zoom-in', shouldBlur(selected.nsfw_level) && !revealed.has(selected.id) ? 'blur-md' : '']"
                @click="openLightbox(selected)" />
              <div>
                <div class="text-color font-semibold">{{ selected.civitai_name }}
                  <span class="text-color-secondary font-normal">· {{ selected.civitai_base }} · {{ selected.civitai_type }}</span></div>
                <div v-if="JSON.parse(selected.trigger_words || '[]').length" class="text-color-secondary mt-1">
                  {{ t("library.triggerWords") }}<code v-for="tw in JSON.parse(selected.trigger_words)" :key="tw" class="mr-1 px-1 bg-surface-hover rounded">{{ tw }}</code></div>
                <a :href="selected.civitai_url" target="_blank" @click="isDesktop && ($event.preventDefault(), openExternal(selected.civitai_url))" class="text-primary text-[11px]">{{ t("library.viewOnCivitai") }}</a>
              </div>
            </div>
          </div>
          <div class="text-color-secondary font-semibold mt-2">{{ t("library.refBy", { n: selected.workflows.length }) }}</div>
          <div v-for="w in selected.workflows" :key="w.id" class="text-color-secondary">· {{ w.filename }}</div>
          <div v-if="!selected.workflows.length" class="text-orange-400">{{ t("library.noRef") }}</div>
        </div>
      </div>
    </div>
    <div v-if="lightbox" class="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-6 cursor-zoom-out"
      @click="closeLightbox">
      <img :src="'/api/preview/' + lightbox.sha256 + '?hd=1'"
        :class="['max-w-full max-h-full rounded shadow-2xl', shouldBlur(lightbox.nsfw_level) && !revealed.has(lightbox.id) ? 'blur-2xl cursor-pointer' : '']"
        @click.stop="reveal(lightbox.id)" />
      <button @click.stop="closeLightbox" class="absolute top-3 right-5 text-white/80 hover:text-white text-3xl leading-none">×</button>
    </div>
  </div>
</template>
