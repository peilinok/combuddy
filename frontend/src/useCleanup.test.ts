import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { effectScope, nextTick } from "vue";
vi.mock("./api", () => ({
  fetchStats: vi.fn().mockResolvedValue({ scanning: false, scan: { phase: "idle" } }),
  fetchUnreferenced: vi.fn().mockResolvedValue({ models: [{ id: 1, filename: "a", size: 100 }, { id: 2, filename: "b", size: 50 }] }),
  postTrash: vi.fn().mockResolvedValue({ moved: [1], skipped: [] }),
}));
import { useCleanup } from "./useCleanup";
import { stats } from "./useScanStatus";

let stop: (() => void) | null = null;
beforeEach(() => {
  stats.value = { scanning: false, scan: { phase: "idle", revision: 0 } };
});
afterEach(() => { stop?.(); stop = null; });

function make() {
  const scope = effectScope();
  const cleanup = scope.run(useCleanup)!;
  stop = () => scope.stop();
  return cleanup;
}

describe("useCleanup", () => {
  it("toggle tracks selected bytes", async () => {
    const c = make(); await c.load();
    c.toggle(1); c.toggle(2);
    expect(c.selectedBytes.value).toBe(150);
    c.toggle(1);
    expect(c.selectedBytes.value).toBe(50);
  });
  it("trashSelected reloads", async () => {
    const c = make(); await c.load(); c.toggle(1);
    await c.trashSelected();
    const api = await import("./api");
    expect(api.postTrash).toHaveBeenCalledWith([1]);
  });
  it("reloads when scanning finishes", async () => {
    const api = await import("./api");
    make();
    (api.fetchUnreferenced as any).mockClear();

    stats.value = { scanning: true, scan: { phase: "scanning", revision: 0 } };
    await nextTick();
    expect(api.fetchUnreferenced).not.toHaveBeenCalled();

    stats.value = { scanning: false, scan: { phase: "idle", revision: 1 } };
    await nextTick();
    expect(api.fetchUnreferenced).toHaveBeenCalledTimes(1);
  });
  it("reloads when revision changes while scanning stays idle", async () => {
    const api = await import("./api");
    make();
    (api.fetchUnreferenced as any).mockClear();

    stats.value = { scanning: false, scan: { phase: "idle", revision: 1 } };
    await nextTick();
    expect(api.fetchUnreferenced).toHaveBeenCalledTimes(1);
  });
});
