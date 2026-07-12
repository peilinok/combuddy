import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchStats = vi.fn();
vi.mock("./api", () => ({ fetchStats }));

const active = { model_count: 1, scanning: true, scan: { phase: "scanning" } };
const idle = { model_count: 1, scanning: false, scan: { phase: "idle" } };

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  fetchStats.mockReset();
});

afterEach(() => { vi.useRealTimers(); });

async function boot() {
  return import("./useScanStatus");
}

describe("useScanStatus", () => {
  it("includes duplicate waste and revision in the initial stats shape", async () => {
    const { stats, scanRevision } = await boot();
    expect(stats.value.duplicate_waste).toBe(0);
    expect(stats.value.scan.revision).toBe(0);
    expect(scanRevision.value).toBe(0);
  });

  it("exposes the revision returned by refresh", async () => {
    fetchStats.mockResolvedValue({ ...idle, scan: { phase: "idle", revision: 4 } });
    const { refresh, scanRevision } = await boot();
    await refresh();
    expect(scanRevision.value).toBe(4);
  });

  it("starts one polling loop across repeated calls and polls active scans every 1500ms", async () => {
    fetchStats.mockResolvedValue(active);
    const { useScanStatus } = await boot();
    const first = useScanStatus();
    const second = useScanStatus();

    await vi.advanceTimersByTimeAsync(0);
    expect(first.stats).toBe(second.stats);
    expect(first.scanning.value).toBe(true);
    expect(fetchStats).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1499);
    expect(fetchStats).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchStats).toHaveBeenCalledTimes(2);
  });

  it("polls idle scans every 10000ms", async () => {
    fetchStats.mockResolvedValue(idle);
    const { useScanStatus } = await boot();
    useScanStatus();

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchStats).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1500);
    expect(fetchStats).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(8500);
    expect(fetchStats).toHaveBeenCalledTimes(2);
  });

  it("deduplicates concurrent refreshes", async () => {
    let resolve!: (value: any) => void;
    fetchStats.mockImplementation(() => new Promise((r) => { resolve = r; }));
    const { refresh } = await boot();

    const first = refresh();
    const second = refresh();
    expect(fetchStats).toHaveBeenCalledTimes(1);

    resolve(idle);
    await Promise.all([first, second]);
    expect(fetchStats).toHaveBeenCalledTimes(1);
  });
});
