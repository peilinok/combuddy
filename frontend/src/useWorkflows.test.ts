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
});
