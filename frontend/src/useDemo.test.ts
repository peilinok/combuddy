import { describe, it, expect, vi, beforeEach } from "vitest";

const fetchStats = vi.fn();
vi.mock("./api", () => ({ fetchStats }));

// mock 的 promise 链要经过几个 microtask 才落地,用宏任务把队列冲空比数 tick 更可靠
const flush = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  vi.resetModules();   // 丢掉已加载的 useDemo,使下面的动态 import 重跑模块级初始化(重置 started 标记)
  fetchStats.mockReset();
});

describe("useDemo", () => {
  it("defaults to false", async () => {
    const { demo } = await import("./useDemo");
    expect(demo.value).toBe(false);
  });
  it("sets demo=true once /api/stats resolves demo:true", async () => {
    fetchStats.mockResolvedValue({ demo: true });
    const { demo, useDemo } = await import("./useDemo");
    useDemo();
    await flush();
    expect(demo.value).toBe(true);
  });
  it("stays false when /api/stats resolves demo:false", async () => {
    fetchStats.mockResolvedValue({ demo: false });
    const { demo, useDemo } = await import("./useDemo");
    useDemo();
    await flush();
    expect(demo.value).toBe(false);
  });
  it("fetches only once across repeated calls", async () => {
    fetchStats.mockResolvedValue({ demo: true });
    const { useDemo } = await import("./useDemo");
    useDemo(); useDemo(); useDemo();
    await flush();
    expect(fetchStats).toHaveBeenCalledTimes(1);
  });
  it("keeps demo false when the fetch rejects", async () => {
    fetchStats.mockRejectedValue(new Error("HTTP 500"));
    const { demo, useDemo } = await import("./useDemo");
    useDemo();
    await flush();
    expect(demo.value).toBe(false);
  });
});
