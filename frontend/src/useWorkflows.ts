import { ref } from "vue";
import { fetchWorkflows, fetchWorkflowResolution } from "./api";

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
  return { workflows, selected, load, select, error };
}
