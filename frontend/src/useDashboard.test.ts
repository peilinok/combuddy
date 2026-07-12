import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchStats = vi.fn();
const postScan = vi.fn();
const postScanCancel = vi.fn();
vi.mock("./api", () => ({ fetchStats, postScan, postScanCancel }));

const idle = { model_count: 3, scanning: false, scan: { phase: "idle" } };

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  fetchStats.mockReset().mockResolvedValue(idle);
  postScan.mockReset().mockResolvedValue({ started: true });
  postScanCancel.mockReset().mockResolvedValue({ ok: true });
});

afterEach(() => { vi.useRealTimers(); });

async function make() {
  const { useDashboard } = await import("./useDashboard");
  return useDashboard();
}

describe("useDashboard", () => {
  it("refreshes shared scan stats", async () => {
    const first = await make();
    const second = await make();
    await vi.advanceTimersByTimeAsync(0);

    expect(first.stats).toBe(second.stats);
    expect(first.stats.value.model_count).toBe(3);
    expect(first.scanning.value).toBe(false);
    expect(fetchStats).toHaveBeenCalledTimes(1);
  });

  it("starts a scan then refreshes stats", async () => {
    const dashboard = await make();
    await vi.advanceTimersByTimeAsync(0);
    fetchStats.mockClear();

    await dashboard.startScan();

    expect(postScan).toHaveBeenCalledTimes(1);
    expect(fetchStats).toHaveBeenCalledTimes(1);
  });

  it("reports a start error without refreshing", async () => {
    postScan.mockRejectedValueOnce(new Error("HTTP 409"));
    const dashboard = await make();
    await vi.advanceTimersByTimeAsync(0);
    fetchStats.mockClear();

    await expect(dashboard.startScan()).resolves.toBeUndefined();

    expect(dashboard.error.value).toContain("HTTP 409");
    expect(fetchStats).not.toHaveBeenCalled();
  });

  it("cancels a scan and refreshes even when cancellation fails", async () => {
    postScanCancel.mockRejectedValueOnce(new Error("HTTP 500"));
    const dashboard = await make();
    await vi.advanceTimersByTimeAsync(0);
    fetchStats.mockClear();

    await expect(dashboard.cancelHash()).resolves.toBeUndefined();

    expect(postScanCancel).toHaveBeenCalledTimes(1);
    expect(fetchStats).toHaveBeenCalledTimes(1);
  });
});
