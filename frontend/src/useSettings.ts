import { ref } from "vue";
import { getSettings, setSettings, getRoots, setRoots, deleteRoot } from "./api";

let writeTail = Promise.resolve();
function enqueueSettingsWrite(patch: Record<string, unknown>) {
  const request = writeTail.then(() => setSettings(patch));
  writeTail = request.then(() => undefined, () => undefined);
  return request;
}

export function useSettings() {
  const settings = ref<any>({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
  const roots = ref<any[]>([]);
  const error = ref<string | null>(null);
  const saveState = ref<"idle" | "saving" | "saved">("idle");
  const addResult = ref<{ ok: boolean; reason: string | null } | null>(null);
  let pending: Record<string, unknown> = {};
  let saveTimer: number | undefined;
  let savedTimer: number | undefined;
  let inFlight = false;
  let flushDue = false;
  let revision = 0;
  let rootsSeq = 0;
  const hasPending = () => Object.keys(pending).length > 0;
  async function load() {
    const startedAt = revision;
    const rootsRequest = ++rootsSeq;
    const dirtyAtStart = inFlight || hasPending();
    try { const [s, r] = await Promise.all([getSettings(), getRoots()]);
      if (!dirtyAtStart && startedAt === revision && !inFlight && !hasPending()) { settings.value = s; error.value = null; }
      if (rootsRequest === rootsSeq) roots.value = r.roots ?? [];
    } catch (e) { error.value = String(e); }
  }
  async function flush() {
    if (inFlight) { flushDue = true; return; }
    if (!hasPending()) return;
    const patch = pending; pending = {}; inFlight = true; flushDue = false;
    try {
      const response = await enqueueSettingsWrite(patch); inFlight = false; error.value = null;
      settings.value = { ...response, ...pending };
      if (hasPending()) { saveState.value = "saving"; if (flushDue) void flush(); return; }
      saveState.value = "saved";
      const savedRevision = revision;
      if (savedTimer !== undefined) clearTimeout(savedTimer);
      savedTimer = globalThis.setTimeout(() => {
        savedTimer = undefined;
        if (savedRevision === revision && !inFlight && !hasPending()) saveState.value = "idle";
      }, 1500);
    } catch (e) {
      inFlight = false; pending = { ...patch, ...pending }; flushDue = false;
      if (saveTimer !== undefined) { clearTimeout(saveTimer); saveTimer = undefined; }
      error.value = String(e); saveState.value = "idle";
    }
  }
  function save(patch: Record<string, unknown>) {
    revision += 1; Object.assign(settings.value, patch); Object.assign(pending, patch);
    if (savedTimer !== undefined) { clearTimeout(savedTimer); savedTimer = undefined; }
    saveState.value = "saving";
    if (saveTimer !== undefined) clearTimeout(saveTimer);
    saveTimer = globalThis.setTimeout(() => {
      saveTimer = undefined;
      if (inFlight) { flushDue = true; return; }
      void flush();
    }, 400);
  }
  async function addRoot(kind: string, path: string) {
    const rootsRequest = ++rootsSeq;
    try {
      const r = await setRoots([{ kind, path, source: "manual" }]);
      addResult.value = r.results?.[0] ?? { ok: true, reason: null };
      const g = await getRoots();
      if (rootsRequest === rootsSeq) roots.value = g.roots ?? [];
      error.value = null;
      return addResult.value.ok;
    } catch (e) { error.value = String(e); return false; }
  }
  async function removeRoot(id: number) {
    const rootsRequest = ++rootsSeq;
    try {
      await deleteRoot(id); const g = await getRoots();
      if (rootsRequest === rootsSeq) roots.value = g.roots ?? [];
      error.value = null;
    }
    catch (e) { error.value = String(e); }
  }
  return { settings, roots, error, saveState, addResult, load, save, addRoot, removeRoot };
}
