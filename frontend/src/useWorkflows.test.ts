import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  fetchWorkflows: vi.fn().mockResolvedValue({ workflows: [{ id: 1, filename: "w.json", resolved: 2, missing: 1 }] }),
  fetchWorkflowResolution: vi.fn().mockResolvedValue({ id: 1, filename: "w.json",
    edges: [{ ref_string: "a", status: "path" }, { ref_string: "b", status: "missing" }] }),
}));
import { useWorkflows } from "./useWorkflows";

describe("useWorkflows", () => {
  it("select loads resolution", async () => {
    const w = useWorkflows(); await w.load(); await w.select(1);
    expect(w.selected.value.edges.length).toBe(2);
  });
  it("select drops a stale successful response", async () => {
    const api = await import("./api");
    let resolveFirst!: (v: any) => void;
    (api.fetchWorkflowResolution as any)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res; }))
      .mockResolvedValueOnce({ id: 2, filename: "new.json", edges: [] });
    const w = useWorkflows();
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
    const w = useWorkflows();
    w.error.value = "old error";
    const first = w.select(3);
    await w.select(4);
    rejectFirst(new Error("stale error"));
    await first;
    expect(w.selected.value.id).toBe(4);
    expect(w.error.value).toBeNull();
  });
});
