import { ref, watch } from "vue";
import { fetchWorkflows, fetchWorkflowResolution } from "./api";
import { scanning, scanRevision } from "./useScanStatus";

export function useWorkflows() {
  const workflows = ref<any[]>([]);
  const selected = ref<any | null>(null);
  const error = ref<string | null>(null);
  let selectSeq = 0;
  async function load() {
    try { workflows.value = (await fetchWorkflows()).workflows; error.value = null; }
    catch (e) { error.value = String(e); }
  }
  async function select(id: number) {
    const my = ++selectSeq;
    try {
      const resolution = await fetchWorkflowResolution(id);
      if (my !== selectSeq) return;
      selected.value = resolution; error.value = null;
    } catch (e) { if (my === selectSeq) error.value = String(e); }
  }
  watch([scanning, scanRevision], async ([now, revision], [was, previousRevision]) => {
    if (!(was && !now) && revision === previousRevision) return;
    const selectedId = selected.value?.id;
    await load();
    if (selectedId == null) return;
    if (workflows.value.some((w) => w.id === selectedId)) await select(selectedId);
    else selected.value = null;
  });
  return { workflows, selected, load, select, error };
}
