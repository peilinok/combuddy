import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const fetchStats = vi.fn();
vi.mock("./api", () => ({ fetchStats }));
const flush = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => { vi.resetModules(); fetchStats.mockReset(); fetchStats.mockResolvedValue({}); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("useDesktop", () => {
  it("isDesktop false with no pywebview and methods no-op safely", async () => {
    vi.stubGlobal("window", {} as any);
    const { isDesktop, useDesktop } = await import("./useDesktop");
    const d = useDesktop();
    await flush();
    expect(isDesktop.value).toBe(false);
    expect(await d.pickFolder()).toBe(null);
    expect(await d.reveal("/x")).toBe(false);
    expect(await d.openExternal("http://x")).toBe(false);
  });

  it("isDesktop true when window.pywebview already present", async () => {
    vi.stubGlobal("window", { pywebview: { api: {} }, addEventListener: vi.fn() } as any);
    const { isDesktop, useDesktop } = await import("./useDesktop");
    useDesktop();
    await flush();
    expect(isDesktop.value).toBe(true);
  });

  it("isDesktop flips true on pywebviewready event", async () => {
    let handler: any = null;
    vi.stubGlobal("window", { addEventListener: (n: string, h: any) => { if (n === "pywebviewready") handler = h; } } as any);
    const { isDesktop, useDesktop } = await import("./useDesktop");
    useDesktop();
    handler();
    expect(isDesktop.value).toBe(true);
  });

  it("pickFolder delegates to window.pywebview.api.pick_folder", async () => {
    const pick = vi.fn().mockResolvedValue("/picked");
    vi.stubGlobal("window", { pywebview: { api: { pick_folder: pick } }, addEventListener: vi.fn() } as any);
    const { useDesktop } = await import("./useDesktop");
    expect(await useDesktop().pickFolder()).toBe("/picked");
  });

  it("update fills from /api/stats after mount", async () => {
    vi.useFakeTimers();
    fetchStats.mockResolvedValue({ update: { version: "9.9.9", url: "http://x" } });
    vi.stubGlobal("window", { pywebview: { api: {} }, addEventListener: vi.fn() } as any);
    const { update, useDesktop } = await import("./useDesktop");
    useDesktop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(update.value?.version).toBe("9.9.9");
    vi.useRealTimers();
  });
});
