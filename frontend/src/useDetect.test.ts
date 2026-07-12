import { describe, it, expect, vi, beforeEach } from "vitest";

const fetchDetect = vi.fn(); const setRoots = vi.fn(); const postScan = vi.fn();
vi.mock("./api", () => ({ fetchDetect, setRoots, postScan }));
const flush = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => { vi.resetModules(); fetchDetect.mockReset(); setRoots.mockReset(); postScan.mockReset();
  setRoots.mockImplementation((roots: any[]) => Promise.resolve({
    ok: true, results: roots.map((r) => ({ path: r.path, ok: true, reason: null })) }));
  postScan.mockResolvedValue({}); });

describe("useDetect", () => {
  it("load fills candidates + skipped, all selected by default", async () => {
    fetchDetect.mockResolvedValue({ candidates: [
      { kind: "model", path: "/a", label: "A", model_count: 5, count_capped: false },
      { kind: "workflow", path: "/w", label: "W", model_count: null, count_capped: false }],
      skipped_config_mappings: 2 });
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load(); await flush();
    expect(d.candidates.value.length).toBe(2);
    expect(d.skipped.value).toBe(2);
    expect(d.selected.value.size).toBe(2);        // default select-all
  });

  it("toggle removes/re-adds a path from selection", async () => {
    fetchDetect.mockResolvedValue({ candidates: [
      { kind: "model", path: "/a", label: "A", model_count: 1, count_capped: false }],
      skipped_config_mappings: 0 });
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load();
    d.toggle("/a"); expect(d.selected.value.has("/a")).toBe(false);
    d.toggle("/a"); expect(d.selected.value.has("/a")).toBe(true);
  });

  it("confirm posts selected roots then triggers scan", async () => {
    fetchDetect.mockResolvedValue({ candidates: [
      { kind: "model", path: "/a", label: "A", model_count: 1, count_capped: false },
      { kind: "model", path: "/b", label: "B", model_count: 1, count_capped: false }],
      skipped_config_mappings: 0 });
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load();
    d.toggle("/b");                                // deselect /b
    await d.confirm();
    expect(setRoots).toHaveBeenCalledWith([{ kind: "model", path: "/a", source: "detected" }]);
    expect(postScan).toHaveBeenCalledTimes(1);
  });

  it("load surfaces errors and does not throw", async () => {
    fetchDetect.mockRejectedValue(new Error("HTTP 500"));
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load(); await flush();
    expect(d.error.value).toContain("500");
    expect(d.candidates.value).toEqual([]);
  });

  it("confirm does not scan when nothing selected", async () => {
    fetchDetect.mockResolvedValue({ candidates: [
      { kind: "model", path: "/a", label: "A", model_count: 1, count_capped: false }],
      skipped_config_mappings: 0 });
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load();
    d.toggle("/a");                                // deselect the only one
    await d.confirm();
    expect(setRoots).not.toHaveBeenCalled();
    expect(postScan).not.toHaveBeenCalled();
  });

  it("confirm keeps setup open when every root fails validation", async () => {
    fetchDetect.mockResolvedValue({ candidates: [
      { kind: "model", path: "/gone", label: "Gone", model_count: 1, count_capped: false }],
      skipped_config_mappings: 0 });
    setRoots.mockResolvedValueOnce({ ok: true, results: [
      { path: "/gone", ok: false, reason: "not_a_directory" }] });
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load();

    expect(await d.confirm()).toBe(false);
    expect(d.error.value).toBe("not_a_directory");
    expect(postScan).not.toHaveBeenCalled();
  });

  it("confirm scans when at least one root passes validation", async () => {
    fetchDetect.mockResolvedValue({ candidates: [
      { kind: "model", path: "/ok", label: "OK", model_count: 1, count_capped: false },
      { kind: "workflow", path: "/gone", label: "Gone", model_count: null, count_capped: false }],
      skipped_config_mappings: 0 });
    setRoots.mockResolvedValueOnce({ ok: true, results: [
      { path: "/ok", ok: true, reason: null },
      { path: "/gone", ok: false, reason: "not_a_directory" }] });
    const { useDetect } = await import("./useDetect");
    const d = useDetect(); await d.load();

    expect(await d.confirm()).toBe(true);
    expect(postScan).toHaveBeenCalledTimes(1);
  });
});
