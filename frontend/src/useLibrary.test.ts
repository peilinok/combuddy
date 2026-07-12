import { describe, it, expect, vi } from "vitest";
import { nextTick } from "vue";
vi.mock("./api", () => ({
  fetchStats: vi.fn().mockResolvedValue({ scanning: false, scan: { phase: "idle" } }),
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
  it("openDetail drops a stale successful response", async () => {
    const api = await import("./api");
    let resolveFirst!: (v: any) => void;
    (api.fetchModel as any)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res; }))
      .mockResolvedValueOnce({ id: 2, filename: "new.safetensors", workflows: [] });
    const lib = useLibrary();
    const first = lib.openDetail(1);
    await lib.openDetail(2);
    resolveFirst({ id: 1, filename: "old.safetensors", workflows: [] });
    await first;
    expect(lib.selected.value.id).toBe(2);
  });
  it("openDetail drops stale errors and clears errors on latest success", async () => {
    const api = await import("./api");
    let rejectFirst!: (e: any) => void;
    (api.fetchModel as any)
      .mockImplementationOnce(() => new Promise((_, rej) => { rejectFirst = rej; }))
      .mockResolvedValueOnce({ id: 4, filename: "new.safetensors", workflows: [] });
    const lib = useLibrary();
    lib.error.value = "old error";
    const first = lib.openDetail(3);
    await lib.openDetail(4);
    rejectFirst(new Error("stale error"));
    await first;
    expect(lib.selected.value.id).toBe(4);
    expect(lib.error.value).toBeNull();
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
  it("stale responses are dropped (race guard)", async () => {
    const api = await import("./api");
    let resolveFirst!: (v: any) => void;
    (api.fetchModels as any)
      .mockImplementationOnce(() => new Promise((res) => { resolveFirst = res; }))
      .mockImplementationOnce(() => Promise.resolve({ models: [{ id: 2, filename: "new.safetensors" }] }));
    const lib = useLibrary();
    const p1 = lib.load(); const p2 = lib.load();
    await p2;
    resolveFirst({ models: [{ id: 1, filename: "old.safetensors" }] });
    await p1;
    expect(lib.models.value[0].filename).toBe("new.safetensors");
  });
  it("settings fetched once across loads", async () => {
    const api = await import("./api");
    (api.getSettings as any).mockClear();
    const lib = useLibrary();
    await lib.load(); await lib.load();
    expect(api.getSettings).toHaveBeenCalledTimes(1);
  });
  it("waits for settings before publishing models", async () => {
    const api = await import("./api");
    let resolveSettings!: (v: any) => void;
    (api.getSettings as any).mockImplementationOnce(() => new Promise((res) => { resolveSettings = res; }));
    const lib = useLibrary();
    const pending = lib.load();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(lib.models.value).toEqual([]);
    resolveSettings({ nsfw_blur_threshold: 0 });
    await pending;
    expect(lib.models.value[0].filename).toBe("a.safetensors");
    expect(lib.shouldBlur(1)).toBe(true);
  });
  it("retries settings after failure without publishing stale-threshold models", async () => {
    const api = await import("./api");
    (api.getSettings as any).mockClear();
    (api.getSettings as any)
      .mockRejectedValueOnce(new Error("settings failed"))
      .mockResolvedValueOnce({ nsfw_blur_threshold: 0 });
    const lib = useLibrary();
    await lib.load();
    expect(lib.models.value).toEqual([]);
    expect(lib.error.value).toContain("settings failed");
    await lib.load();
    expect(lib.models.value[0].filename).toBe("a.safetensors");
    expect(api.getSettings).toHaveBeenCalledTimes(2);
  });
  it("resets pagination when library filters change", async () => {
    const lib = useLibrary();
    const changes = [
      () => { lib.search.value = "new"; },
      () => { lib.flag.value = "unknown"; },
      () => { lib.typeFilter.value = "loras"; },
    ];
    for (const change of changes) {
      lib.pageFirst.value = 60;
      change();
      await nextTick();
      expect(lib.pageFirst.value).toBe(0);
    }
  });
});
