<script setup lang="ts">
import { onMounted, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useCleanup } from "../useCleanup";
import { useDuplicates } from "../useDuplicates";
import { useTrash } from "../useTrash";
import { cleanupTab } from "../useNav";
import { humanSize } from "../format";
const { t } = useI18n();
const u = useCleanup();
const d = useDuplicates();
const tr = useTrash();
onMounted(() => { u.load(); d.load(); tr.load(); });
const total = computed(() => u.items.value.reduce((s: number, m: any) => s + m.size, 0));
function reason(g: any, m: any) {
  return m.ref_count > 0 ? t("duplicates.reasonRef") : t("duplicates.reasonPath");
}
function headName(g: any) { return g.members.find((m: any) => m.id === d.keepId(g))?.filename; }
function keepInode(g: any) { return g.members.find((m: any) => m.id === d.keepId(g))?.inode; }
async function onTrash() {
  if (!window.confirm(t("duplicates.confirm", { n: d.selectedIds.value.length }))) return;
  await d.trashSelected();
}
async function onTrashUnref() {
  if (!window.confirm(t("cleanup.confirm", { n: u.selectedIds.value.size, size: humanSize(u.selectedBytes.value) }))) return;
  await u.trashSelected();
}
</script>
<template>
  <div>
    <h1 class="text-xl font-semibold mb-4">{{ t("cleanup.title") }}</h1>
    <div class="flex gap-5 border-b border-surface-border mb-4">
      <button class="pb-2 text-sm" :class="cleanupTab==='unreferenced' ? 'border-b-2 border-primary text-primary' : 'text-color-secondary'"
        @click="cleanupTab='unreferenced'">{{ t("duplicates.tabUnref") }}</button>
      <button class="pb-2 text-sm" :class="cleanupTab==='duplicates' ? 'border-b-2 border-primary text-primary' : 'text-color-secondary'"
        @click="cleanupTab='duplicates'">{{ t("duplicates.tabDup") }} <span class="text-color-secondary">{{ d.groups.value.length || '' }}</span></button>
      <button class="pb-2 text-sm" :class="cleanupTab==='trash' ? 'border-b-2 border-primary text-primary' : 'text-color-secondary'"
        @click="cleanupTab='trash'; tr.load()">{{ t("trash.tab") }} <span class="text-color-secondary">{{ tr.items.value.length || '' }}</span></button>
    </div>

    <!-- 未引用(原样保留) -->
    <div v-if="cleanupTab==='unreferenced'">
      <div v-if="u.error.value" class="text-orange-400 text-sm mb-3">{{ u.error.value }}</div>
      <div class="flex justify-between items-center bg-surface-card rounded-lg p-4 mb-4">
        <div><div class="font-semibold">{{ t("cleanup.unreferencedModels") }}</div>
          <div class="text-xs text-color-secondary">{{ t("cleanup.countUnused", { n: u.items.value.length }) }}</div></div>
        <div class="text-right"><div class="text-orange-400 text-xl font-bold">{{ humanSize(total) }}</div>
          <div class="text-[10px] text-color-secondary">{{ t("cleanup.reclaimable") }}</div></div>
      </div>
      <table class="w-full text-sm"><tbody>
        <tr v-for="m in u.items.value" :key="m.id" class="hover:bg-surface-hover">
          <td class="py-1.5 w-6"><input type="checkbox" :checked="u.selectedIds.value.has(m.id)" @change="u.toggle(m.id)" /></td>
          <td class="text-color">{{ m.filename }}</td><td class="text-color-secondary">{{ m.dir_type }}</td>
          <td class="text-right text-color-secondary">{{ humanSize(m.size) }}</td>
        </tr>
      </tbody></table>
      <div v-if="u.selectedIds.value.size" class="flex justify-between items-center bg-surface-hover rounded-lg p-3 mt-4 sticky bottom-3">
        <span class="text-sm text-color-secondary">{{ t("cleanup.selectedSummary", { n: u.selectedIds.value.size, size: humanSize(u.selectedBytes.value) }) }}</span>
        <button @click="onTrashUnref" class="px-4 py-1.5 rounded bg-primary text-white text-sm font-semibold">{{ t("cleanup.moveToTrash") }}</button>
      </div>
    </div>

    <!-- 重复 -->
    <div v-else-if="cleanupTab==='duplicates'">
      <div v-if="d.error.value" class="text-orange-400 text-sm mb-3">{{ d.error.value }}</div>
      <div class="text-sm text-color-secondary mb-3">
        {{ t("duplicates.summary", { groups: d.groups.value.length, size: humanSize(d.totalReclaimable.value) }) }}
        <span v-if="d.unhashedCount.value" class="ml-2">· {{ t("duplicates.unhashed", { n: d.unhashedCount.value }) }}</span>
      </div>
      <div v-if="!d.groups.value.length" class="text-color-secondary text-sm py-8 text-center">
        {{ d.unhashedCount.value ? t("duplicates.hashing") : t("duplicates.emptyClean") }}
      </div>
      <div v-for="g in d.groups.value" :key="g.sha256" class="bg-surface-card rounded-lg p-4 mb-3">
        <div class="flex items-center gap-2 mb-2 text-sm">
          <i class="pi pi-clone text-color-secondary"></i>
          <span class="font-medium">{{ headName(g) }}</span>
          <span class="text-color-secondary">{{ t("duplicates.perCopy", { count: g.count, size: humanSize(g.size), reclaimable: humanSize(g.reclaimable) }) }}</span>
          <span v-if="g.reclaimable===0" class="text-color-secondary">· {{ t("duplicates.allInUse") }}</span>
        </div>
        <div v-for="m in g.members" :key="m.id" class="flex items-center gap-3 py-1.5 px-2 rounded"
          :class="m.id===d.keepId(g) ? 'bg-surface-hover' : ''">
          <input type="radio" :checked="m.id===d.keepId(g)" @change="d.setKeep(g.sha256, m.id)" />
          <div class="flex-1 min-w-0">
            <div class="text-sm truncate">{{ m.rel_path }}</div>
            <div class="text-xs text-color-secondary truncate">{{ m.root_label }}</div>
          </div>
          <!-- 状态标签,优先级:保留 > 被引用 > 同inode > 待删 -->
          <span v-if="m.id===d.keepId(g)" class="text-[11px] px-2 py-0.5 rounded bg-primary/20 text-primary">{{ t("duplicates.keep") }} · {{ reason(g, m) }}</span>
          <span v-else-if="m.ref_count>0" class="text-[11px] px-2 py-0.5 rounded bg-surface-hover text-color-secondary">{{ t("duplicates.inUse") }}</span>
          <span v-else-if="m.inode === keepInode(g)" class="text-[11px] text-color-secondary flex items-center gap-1" :title="t('duplicates.hardlink')"><i class="pi pi-link"></i></span>
          <span v-else class="text-[11px] text-color-secondary">{{ t("duplicates.pendingDelete") }}</span>
        </div>
      </div>
      <div v-if="d.selectedIds.value.length" class="flex justify-between items-center bg-surface-hover rounded-lg p-3 mt-4 sticky bottom-3">
        <span class="text-sm text-color-secondary">{{ t("duplicates.selectedSummary", { n: d.selectedIds.value.length, size: humanSize(d.selectedBytes.value) }) }}</span>
        <button @click="onTrash" class="px-4 py-1.5 rounded bg-primary text-white text-sm font-semibold">{{ t("duplicates.moveToTrash") }}</button>
      </div>
    </div>

    <!-- 回收站 -->
    <div v-else>
      <div v-if="tr.error.value" class="text-orange-400 text-sm mb-3">{{ tr.error.value }}</div>
      <div v-if="tr.lastRestore.value" class="text-sm text-primary mb-3">
        {{ t("trash.restoreResult", { n: tr.lastRestore.value.restored }) }}
        <span v-if="tr.lastRestore.value.conflict" class="text-orange-400"> · {{ t("trash.restoreConflict", { n: tr.lastRestore.value.conflict }) }}</span>
        <span v-if="tr.lastRestore.value.error" class="text-orange-400"> · {{ t("trash.restoreError", { n: tr.lastRestore.value.error }) }}</span>
      </div>
      <div class="flex justify-between items-center bg-surface-card rounded-lg p-4 mb-4">
        <div><div class="font-semibold">{{ t("trash.title") }}</div>
          <div class="text-xs text-color-secondary">{{ t("trash.hint") }}</div></div>
        <div class="text-right"><div class="text-color text-xl font-bold">{{ humanSize(tr.totalBytes.value) }}</div>
          <div class="text-[10px] text-color-secondary">{{ t("trash.occupied") }}</div></div>
      </div>
      <div v-if="!tr.items.value.length" class="text-color-secondary text-sm py-8 text-center">{{ t("trash.empty") }}</div>
      <table v-else class="w-full text-sm"><tbody>
        <tr v-for="it in tr.items.value" :key="it.id" class="hover:bg-surface-hover">
          <td class="py-1.5 text-color truncate max-w-md" :title="it.model_path">{{ it.model_path }}</td>
          <td class="text-color-secondary">{{ it.dir_type }}</td>
          <td class="text-right text-color-secondary">{{ humanSize(it.size ?? 0) }}</td>
          <td class="text-right text-color-secondary text-xs">{{ new Date(it.trashed_at * 1000).toLocaleString() }}</td>
          <td class="text-right"><button @click="tr.restore([it.id])" :disabled="tr.restoring.value"
            class="text-primary text-xs hover:underline disabled:opacity-50">{{ t("trash.restore") }}</button></td>
        </tr>
      </tbody></table>
    </div>
  </div>
</template>
