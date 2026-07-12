import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
vi.mock("./api", () => ({
  getSettings: vi.fn().mockResolvedValue({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 }),
  setSettings: vi.fn().mockResolvedValue({ auto_hash: true, hash_workers: 3, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 }),
  getRoots: vi.fn().mockResolvedValue({ roots: [{ kind: "model", path: "/m" }] }),
  setRoots: vi.fn().mockResolvedValue({ ok: true, results: [{ path: "/x", ok: true, reason: null }] }),
  deleteRoot: vi.fn().mockResolvedValue({ ok: true }),
}));
import { useSettings } from "./useSettings";
beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());
describe("useSettings", () => {
  it("load pulls settings + roots", async () => {
    const s = useSettings(); await s.load();
    expect(s.settings.value.auto_hash).toBe(true);
    expect(s.roots.value[0].path).toBe("/m");
  });
  it("save applies locally at once, debounces and coalesces the request", async () => {
    const api = await import("./api"); (api.setSettings as any).mockClear(); const s = useSettings();
    s.save({ hash_workers: 2 }); s.save({ hash_workers: 3 });
    expect(s.settings.value.hash_workers).toBe(3);
    expect(api.setSettings).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(400);
    expect(api.setSettings).toHaveBeenCalledTimes(1);
    expect(api.setSettings).toHaveBeenCalledWith({ hash_workers: 3 });
    expect(s.saveState.value).toBe("saved");
    await vi.advanceTimersByTimeAsync(1500);
    expect(s.saveState.value).toBe("idle");
  });
  it("keeps saves single-flight and preserves pending edits over an older response", async () => {
    const api = await import("./api");
    let resolveA!: (value: any) => void;
    (api.setSettings as any).mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => { resolveA = resolve; }))
      .mockResolvedValueOnce({ auto_hash: true, hash_workers: 3, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    const s = useSettings();
    s.save({ hash_workers: 2 });
    await vi.advanceTimersByTimeAsync(400);
    expect(api.setSettings).toHaveBeenCalledTimes(1);
    expect(api.setSettings).toHaveBeenLastCalledWith({ hash_workers: 2 });

    s.save({ hash_workers: 3 });
    await vi.advanceTimersByTimeAsync(400);
    expect(api.setSettings).toHaveBeenCalledTimes(1);
    resolveA({ auto_hash: true, hash_workers: 2, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    await vi.advanceTimersByTimeAsync(0);

    expect(s.settings.value.hash_workers).toBe(3);
    expect(api.setSettings).toHaveBeenCalledTimes(2);
    expect(api.setSettings).toHaveBeenLastCalledWith({ hash_workers: 3 });
    expect(s.saveState.value).toBe("saved");
  });
  it("retains a failed patch and retries it with newer edits taking priority", async () => {
    const api = await import("./api");
    let rejectA!: (reason: unknown) => void;
    (api.setSettings as any).mockReset()
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectA = reject; }))
      .mockResolvedValueOnce({ auto_hash: true, hash_workers: 3, hash_max_mbps: 0, online_enrich: false, nsfw_blur_threshold: 1 });
    const s = useSettings();
    s.save({ auto_hash: false, hash_workers: 2 });
    await vi.advanceTimersByTimeAsync(400);
    rejectA(new Error("save failed"));
    await vi.advanceTimersByTimeAsync(0);

    expect(s.error.value).toContain("save failed");
    expect(s.saveState.value).toBe("idle");
    s.save({ hash_workers: 3, online_enrich: false });
    await vi.advanceTimersByTimeAsync(400);

    expect(api.setSettings).toHaveBeenCalledTimes(2);
    expect(api.setSettings).toHaveBeenLastCalledWith({ auto_hash: false, hash_workers: 3, online_enrich: false });
    expect(s.error.value).toBeNull();
    expect(s.saveState.value).toBe("saved");
  });
  it("does not let an older saved timer clear a newer saving state", async () => {
    const api = await import("./api");
    let resolveB!: (value: any) => void;
    (api.setSettings as any).mockReset()
      .mockResolvedValueOnce({ auto_hash: true, hash_workers: 2, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveB = resolve; }));
    const s = useSettings();
    s.save({ hash_workers: 2 });
    await vi.advanceTimersByTimeAsync(400);
    expect(s.saveState.value).toBe("saved");

    await vi.advanceTimersByTimeAsync(1000);
    s.save({ hash_workers: 3 });
    expect(s.saveState.value).toBe("saving");
    await vi.advanceTimersByTimeAsync(600);

    expect(api.setSettings).toHaveBeenCalledTimes(2);
    expect(s.saveState.value).toBe("saving");
    resolveB({ auto_hash: true, hash_workers: 3, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    await vi.advanceTimersByTimeAsync(0);
    expect(s.saveState.value).toBe("saved");
  });
  it("does not let a late load overwrite a newer optimistic save", async () => {
    const api = await import("./api");
    let resolveSettings!: (value: any) => void;
    (api.getSettings as any).mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSettings = resolve; }));
    (api.getRoots as any).mockReset().mockResolvedValueOnce({ roots: [{ kind: "model", path: "/late" }] });
    const s = useSettings();
    const loading = s.load();
    s.save({ hash_workers: 3 });
    resolveSettings({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    await loading;

    expect(s.settings.value.hash_workers).toBe(3);
    expect(s.roots.value[0].path).toBe("/late");
  });
  it("does not publish settings from a load started during an in-flight save", async () => {
    const api = await import("./api");
    let resolvePost!: (value: any) => void;
    let resolveGet!: (value: any) => void;
    (api.setSettings as any).mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => { resolvePost = resolve; }));
    (api.getSettings as any).mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => { resolveGet = resolve; }));
    (api.getRoots as any).mockReset().mockResolvedValueOnce({ roots: [{ kind: "model", path: "/during-save" }] });
    const s = useSettings();
    s.save({ hash_workers: 2 });
    await vi.advanceTimersByTimeAsync(400);
    const loading = s.load();

    resolvePost({ auto_hash: true, hash_workers: 2, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    await vi.advanceTimersByTimeAsync(0);
    resolveGet({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    await loading;

    expect(s.settings.value.hash_workers).toBe(2);
    expect(s.roots.value[0].path).toBe("/during-save");
  });
  it("serializes settings writes across useSettings instances", async () => {
    const api = await import("./api");
    let resolveA!: (value: any) => void;
    (api.setSettings as any).mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => { resolveA = resolve; }))
      .mockResolvedValueOnce({ auto_hash: true, hash_workers: 2, hash_max_mbps: 0, online_enrich: false, nsfw_blur_threshold: 1 });
    const a = useSettings(); const b = useSettings();
    a.save({ hash_workers: 2 });
    await vi.advanceTimersByTimeAsync(400);
    expect(api.setSettings).toHaveBeenCalledTimes(1);
    expect(api.setSettings).toHaveBeenNthCalledWith(1, { hash_workers: 2 });

    b.save({ online_enrich: false });
    await vi.advanceTimersByTimeAsync(400);
    expect(api.setSettings).toHaveBeenCalledTimes(1);
    resolveA({ auto_hash: true, hash_workers: 2, hash_max_mbps: 0, online_enrich: true, nsfw_blur_threshold: 1 });
    await vi.advanceTimersByTimeAsync(0);

    expect(api.setSettings).toHaveBeenCalledTimes(2);
    expect(api.setSettings).toHaveBeenNthCalledWith(2, { online_enrich: false });
  });
  it("addRoot surfaces duplicate result", async () => {
    const api = await import("./api");
    (api.setRoots as any).mockReset()
      .mockResolvedValueOnce({ ok: true, results: [{ path: "/m", ok: false, reason: "duplicate" }] });
    (api.getRoots as any).mockReset().mockResolvedValueOnce({ roots: [{ kind: "model", path: "/m" }] });
    const s = useSettings();
    const ok = await s.addRoot("model", "/m");
    expect(api.setRoots).toHaveBeenCalledTimes(1);
    expect(ok).toBe(false);
    expect(s.addResult.value?.reason).toBe("duplicate");
  });
  it("removeRoot deletes then reloads roots", async () => {
    const api = await import("./api");
    (api.deleteRoot as any).mockReset().mockResolvedValueOnce({ ok: true });
    (api.getRoots as any).mockReset().mockResolvedValueOnce({ roots: [] });
    const s = useSettings();
    await s.removeRoot(5);
    expect(api.deleteRoot).toHaveBeenCalledTimes(1);
    expect(api.deleteRoot).toHaveBeenCalledWith(5);
    expect(api.getRoots).toHaveBeenCalledTimes(1);
  });
});
