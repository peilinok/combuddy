import { ref, computed, watch } from "vue";
import { fetchDuplicates, postTrash } from "./api";
import { scanning, scanRevision } from "./useScanStatus";

export function reclaimableOf(members: any[], keepId: number): number {
  const keepInode = members.find((m) => m.id === keepId)?.inode;   // 相对当前保留项
  const del = members.filter((m) => m.ref_count === 0 && m.id !== keepId && m.inode !== keepInode);
  const seen = new Set<string>(); let sum = 0;
  for (const m of del) if (!seen.has(m.inode)) { seen.add(m.inode); sum += m.size; }
  return sum;
}

export function useDuplicates() {
  const groups = ref<any[]>([]);
  const keepIds = ref<Map<string, number>>(new Map());
  const unhashedCount = ref(0);
  const totalReclaimable = ref(0);
  const error = ref<string | null>(null);

  function keepId(g: any): number { return keepIds.value.get(g.sha256) ?? g.suggested_keep_id; }
  function deleteIdsOf(g: any): number[] {
    const k = keepId(g);
    const ki = g.members.find((m: any) => m.id === k)?.inode;
    return g.members.filter((m: any) => m.ref_count === 0 && m.id !== k && m.inode !== ki).map((m: any) => m.id);
  }
  const selectedIds = computed(() => groups.value.flatMap((g) => deleteIdsOf(g)));
  const selectedBytes = computed(() =>
    groups.value.reduce((s, g) => s + reclaimableOf(g.members, keepId(g)), 0));

  async function load() {
    try {
      const r = await fetchDuplicates();
      groups.value = r.groups; unhashedCount.value = r.unhashed_count;
      totalReclaimable.value = r.total_reclaimable;
      const m = new Map<string, number>();
      for (const g of r.groups) m.set(g.sha256, g.suggested_keep_id);
      keepIds.value = m;
      error.value = null;
    } catch (e) { error.value = String(e); }
  }
  function setKeep(sha256: string, memberId: number) {
    const m = new Map(keepIds.value); m.set(sha256, memberId); keepIds.value = m;
  }
  async function trashSelected() {
    try {
      const res = await postTrash([...selectedIds.value]);
      const skippedWarning = res.skipped?.length ? `${res.skipped.length} 项因所在磁盘只读/离线未能移动` : null;
      await load();
      if (skippedWarning) error.value = skippedWarning;
    } catch (e) { error.value = String(e); }
  }
  watch([scanning, scanRevision], ([now, revision], [was, previousRevision]) => {
    if ((was && !now) || revision !== previousRevision) load();
  });
  return { groups, keepIds, unhashedCount, totalReclaimable, error,
           selectedBytes, selectedIds, keepId, deleteIdsOf, setKeep, trashSelected, load };
}
