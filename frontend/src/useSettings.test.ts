import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  getSettings: vi.fn().mockResolvedValue({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 }),
  setSettings: vi.fn().mockResolvedValue({ auto_hash: false, hash_workers: 3, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 }),
  getRoots: vi.fn().mockResolvedValue({ roots: [{ kind: "model", path: "/m" }] }),
  setRoots: vi.fn().mockResolvedValue({ ok: true }),
}));
import { useSettings } from "./useSettings";

describe("useSettings", () => {
  it("load pulls settings + roots", async () => {
    const s = useSettings(); await s.load();
    expect(s.settings.value.auto_hash).toBe(true);
    expect(s.roots.value[0].path).toBe("/m");
  });
  it("save reflects server value", async () => {
    const api = await import("./api"); const s = useSettings();
    await s.save({ hash_workers: 3 });
    expect(api.setSettings).toHaveBeenCalledWith({ hash_workers: 3 });
    expect(s.settings.value.hash_workers).toBe(3);
  });
});
