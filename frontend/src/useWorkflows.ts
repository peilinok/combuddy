import { ref } from "vue";
import { fetchWorkflows, fetchWorkflowResolution } from "./api";

export function useWorkflows() {
  const workflows = ref<any[]>([]);
  const selected = ref<any | null>(null);
  const error = ref<string | null>(null);
  async function load() {
    try { workflows.value = (await fetchWorkflows()).workflows; error.value = null; }
    catch (e) { error.value = String(e); }
  }
  async function select(id: number) {
    try { selected.value = await fetchWorkflowResolution(id); } catch (e) { error.value = String(e); }
  }
  return { workflows, selected, load, select, error };
}
