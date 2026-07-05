import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  fetchStats: vi.fn().mockResolvedValue({ model_count: 3, scanning: false }),
  postScan: vi.fn().mockResolvedValue({ started: true }),
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
});
