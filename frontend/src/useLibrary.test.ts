import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  fetchModels: vi.fn().mockResolvedValue({ models: [
    { id: 1, filename: "a.safetensors", label: "sdxl", ref_count: 2,
      civitai_found: 1, civitai_name: "Real", nsfw_level: 4, sha256: "x", has_preview: 1 }] }),
  fetchModel: vi.fn().mockResolvedValue({ id: 1, filename: "a.safetensors", workflows: [{ id: 9, filename: "w.json" }] }),
  getSettings: vi.fn().mockResolvedValue({ nsfw_blur_threshold: 1 }),
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
  it("load pulls models + settings; shouldBlur uses threshold", async () => {
    const lib = useLibrary();
    await lib.load();
    expect(lib.models.value[0].civitai_name).toBe("Real");
    expect(lib.shouldBlur(4)).toBe(true);    // 4 > 1
    expect(lib.shouldBlur(1)).toBe(false);   // 1 不 > 1
  });
  it("reveal unblurs one id", async () => {
    const lib = useLibrary();
    lib.reveal(1);
    expect(lib.revealed.value.has(1)).toBe(true);
  });
  it("openLightbox/closeLightbox toggles the zoomed model", () => {
    const lib = useLibrary();
    lib.openLightbox({ id: 1, sha256: "x", nsfw_level: 4 });
    expect(lib.lightbox.value.id).toBe(1);
    lib.closeLightbox();
    expect(lib.lightbox.value).toBe(null);
  });
  it("layout 默认 grid", () => {
    const lib = useLibrary();
    expect(lib.layout.value).toBe("grid");
  });
  it("typeCounts 按 dir_type 计数", async () => {
    const lib = useLibrary();
    lib.models.value = [
      { id: 1, dir_type: "checkpoints", filename: "a.safetensors", display_name: "A" },
      { id: 2, dir_type: "checkpoints", filename: "b.safetensors", display_name: "B" },
      { id: 3, dir_type: "loras", filename: "c.safetensors", display_name: "C" },
    ];
    expect(lib.typeCounts.value.length).toBe(2);
    const checkpoints = lib.typeCounts.value.find((t: any) => t.dir_type === "checkpoints");
    const loras = lib.typeCounts.value.find((t: any) => t.dir_type === "loras");
    expect(checkpoints.count).toBe(2);
    expect(loras.count).toBe(1);
  });
  it("typeFilter='loras' 时 visibleModels 只剩该类", async () => {
    const lib = useLibrary();
    lib.models.value = [
      { id: 1, dir_type: "checkpoints", filename: "a.safetensors", display_name: "A" },
      { id: 2, dir_type: "checkpoints", filename: "b.safetensors", display_name: "B" },
      { id: 3, dir_type: "loras", filename: "c.safetensors", display_name: "C" },
    ];
    lib.typeFilter.value = "loras";
    expect(lib.visibleModels.value.length).toBe(1);
    expect(lib.visibleModels.value[0].id).toBe(3);
  });
});
