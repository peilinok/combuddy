import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  fetchStats: vi.fn().mockResolvedValue({ model_count: 3, scanning: false }),
  postScan: vi.fn().mockResolvedValue({ started: true }),
  postScanCancel: vi.fn().mockResolvedValue({ ok: true }),
  getSettings: vi.fn().mockResolvedValue({ auto_hash: true, hash_workers: 1, hash_max_mbps: 0 }),
  setSettings: vi.fn().mockResolvedValue({ auto_hash: false, hash_workers: 3, hash_max_mbps: 0 }),
}));
import { useDashboard } from "./useDashboard";

describe("useDashboard", () => {
  it("refresh loads stats", async () => {
    const d = useDashboard();
    await d.refresh();
    expect(d.stats.value.model_count).toBe(3);
    expect(d.scanning.value).toBe(false);
  });
  it("startScan calls postScan then refreshes", async () => {
    const api = await import("./api");
    const d = useDashboard();
    await d.startScan();
    expect(api.postScan).toHaveBeenCalled();
  });
  it("startScan sets error and does not throw when postScan rejects", async () => {
    const api = await import("./api");
    (api.postScan as any).mockRejectedValueOnce(new Error("HTTP 409"));
    const d = useDashboard();
    await expect(d.startScan()).resolves.toBeUndefined();
    expect(d.error.value).toBeTruthy();
  });
  it("loadSettings pulls the settings dict", async () => {
    const d = useDashboard();
    await d.loadSettings();
    expect(d.settings.value.auto_hash).toBe(true);
    expect(d.settings.value.hash_workers).toBe(1);
  });
  it("saveSettings writes and reflects server value", async () => {
    const api = await import("./api");
    const d = useDashboard();
    await d.saveSettings({ hash_workers: 3 });
    expect(api.setSettings).toHaveBeenCalledWith({ hash_workers: 3 });
    expect(d.settings.value.hash_workers).toBe(3);
  });
  it("cancelHash calls postScanCancel", async () => {
    const api = await import("./api");
    const d = useDashboard();
    await d.cancelHash();
    expect(api.postScanCancel).toHaveBeenCalled();
  });
});
