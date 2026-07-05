import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  fetchModels: vi.fn().mockResolvedValue({ models: [{ id: 1, filename: "a.safetensors", label: "sdxl", ref_count: 2 }] }),
  fetchModel: vi.fn().mockResolvedValue({ id: 1, filename: "a.safetensors", workflows: [{ id: 9, filename: "w.json" }] }),
}));
import { useLibrary } from "./useLibrary";

describe("useLibrary", () => {
  it("load fills models", async () => {
    const lib = useLibrary(); await lib.load();
    expect(lib.models.value[0].filename).toBe("a.safetensors");
  });
  it("openDetail fetches reverse deps", async () => {
    const lib = useLibrary(); await lib.openDetail(1);
    expect(lib.selected.value.workflows[0].filename).toBe("w.json");
  });
});
