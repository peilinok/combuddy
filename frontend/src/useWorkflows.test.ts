import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { effectScope, nextTick } from "vue";
vi.mock("./api", () => ({
  fetchStats: vi.fn().mockResolvedValue({ scanning: false, scan: { phase: "idle", revision: 0 } }),
  fetchWorkflows: vi.fn().mockResolvedValue({ workflows: [{ id: 1, filename: "w.json", resolved: 2, missing: 1 }] }),
  fetchWorkflowResolution: vi.fn().mockResolvedValue({ id: 1, filename: "w.json",
    edges: [{ ref_string: "a", status: "path" }, { ref_string: "b", status: "missing" }] }),
}));
import { useWorkflows } from "./useWorkflows";
import { stats } from "./useScanStatus";

let stop: (() => void) | null = null;
beforeEach(() => {
  stats.value = { scanning: false, scan: { phase: "idle", revision: 0 } };
});
afterEach(() => { stop?.(); stop = null; });

function make() {
  const scope = effectScope();
  const workflows = scope.run(useWorkflows)!;
  stop = () => scope.stop();
  return workflows;
}

describe("useWorkflows", () => {
  it("select loads resolution", async () => {
    const w = make(); await w.load(); await w.select(1);
    expect(w.selected.value.edges.length).toBe(2);
  });
  it("select drops a stale successful response", async () => {
    const api = await import("./api");
    let resolveFirst!: (v: any) => void;
    (api.fetchWorkflowResolution as any)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res; }))
      .mockResolvedValueOnce({ id: 2, filename: "new.json", edges: [] });
    const w = make();
    const first = w.select(1);
    await w.select(2);
    resolveFirst({ id: 1, filename: "old.json", edges: [] });
    await first;
    expect(w.selected.value.id).toBe(2);
  });
  it("select drops stale errors and clears errors on latest success", async () => {
    const api = await import("./api");
    let rejectFirst!: (e: any) => void;
    (api.fetchWorkflowResolution as any)
      .mockImplementationOnce(() => new Promise((_, rej) => { rejectFirst = rej; }))
      .mockResolvedValueOnce({ id: 4, filename: "new.json", edges: [] });
    const w = make();
    w.error.value = "old error";
    const first = w.select(3);
    await w.select(4);
    rejectFirst(new Error("stale error"));
    await first;
    expect(w.selected.value.id).toBe(4);
    expect(w.error.value).toBeNull();
  });
  it("reloads the list and selected resolution when revision changes", async () => {
    const api = await import("./api");
    const w = make();
    await w.load(); await w.select(1);
    (api.fetchWorkflows as any).mockClear();
    (api.fetchWorkflowResolution as any).mockClear();

    stats.value = { scanning: false, scan: { phase: "idle", revision: 1 } };
    await nextTick();

    expect(api.fetchWorkflows).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(api.fetchWorkflowResolution).toHaveBeenCalledWith(1));
    expect(w.selected.value.id).toBe(1);
  });
  it("does not restore an old selection after the user selects during reload", async () => {
    const api = await import("./api");
    let resolveReload!: (value: any) => void;
    (api.fetchWorkflows as any).mockReset()
      .mockResolvedValueOnce({ workflows: [{ id: 1 }, { id: 2 }] })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveReload = resolve; }));
    (api.fetchWorkflowResolution as any).mockReset()
      .mockImplementation((id: number) => Promise.resolve({ id, filename: `${id}.json`, edges: [] }));
    const w = make();
    await w.load(); await w.select(1);
    (api.fetchWorkflowResolution as any).mockClear();

    stats.value = { scanning: false, scan: { phase: "idle", revision: 1 } };
    await nextTick();
    await w.select(2);
    const reloaded = [{ id: 1, reloaded: true }, { id: 2, reloaded: true }];
    resolveReload({ workflows: reloaded });
    await vi.waitFor(() => expect(w.workflows.value).toEqual(reloaded));

    expect(w.selected.value.id).toBe(2);
    expect((api.fetchWorkflowResolution as any).mock.calls.map((c: any[]) => c[0])).toEqual([2]);
  });
});
